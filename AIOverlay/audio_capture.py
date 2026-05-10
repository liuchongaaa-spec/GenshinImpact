# -*- coding: utf-8 -*-
"""
音频捕获模块 - 系统扬声器回环录制
使用 WASAPI Loopback 在内存中维护一个滚动缓冲区，
按需切取最近 N 秒的音频数据，全程不写磁盘。
"""

import io
import wave
import threading
import numpy as np
import soundcard as sc


class AudioCapture:
    """系统音频滚动缓冲区"""

    def __init__(self, buffer_seconds: int = 30, sample_rate: int = 16000):
        """
        初始化音频捕获器

        Args:
            buffer_seconds: 缓冲区保留的秒数
            sample_rate: 采样率 (Hz)
        """
        self.sample_rate = sample_rate
        self.buffer_seconds = buffer_seconds
        self.channels = 1  # 单声道，节省带宽

        # 环形缓冲区：预分配一个固定大小的 numpy 数组
        self._buffer_size = self.sample_rate * self.buffer_seconds
        self._buffer = np.zeros(self._buffer_size, dtype=np.float32)
        self._write_pos = 0  # 当前写入位置
        self._lock = threading.Lock()

        # 录音线程控制
        self._running = False
        self._thread = None

    def start(self):
        """启动后台录音线程"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()
        print(f"🎤 音频缓冲区已启动 (保留最近 {self.buffer_seconds} 秒)")

    def stop(self):
        """停止录音"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _record_loop(self):
        """后台录音主循环"""
        try:
            # 获取默认扬声器并创建 loopback 录音器
            speaker = sc.default_speaker()
            loopback = sc.get_microphone(
                id=str(speaker.name), include_loopback=True
            )

            # 每次读取 0.1 秒的数据块
            chunk_frames = self.sample_rate // 10

            with loopback.recorder(samplerate=self.sample_rate, channels=[0]) as recorder:
                while self._running:
                    # 读取一块音频数据 (shape: [frames, channels])
                    data = recorder.record(numframes=chunk_frames)

                    # 转为单声道一维数组
                    mono = data[:, 0] if data.ndim > 1 else data

                    with self._lock:
                        # 写入环形缓冲区
                        n = len(mono)
                        end_pos = self._write_pos + n

                        if end_pos <= self._buffer_size:
                            # 不需要绕回
                            self._buffer[self._write_pos:end_pos] = mono
                        else:
                            # 需要绕回到开头
                            first_part = self._buffer_size - self._write_pos
                            self._buffer[self._write_pos:] = mono[:first_part]
                            self._buffer[:n - first_part] = mono[first_part:]

                        self._write_pos = end_pos % self._buffer_size

        except Exception as e:
            print(f"音频捕获异常: {e}")
            self._running = False

    def get_audio_bytes(self) -> bytes:
        """
        获取缓冲区中所有音频数据，转换为 WAV 格式的字节流

        Returns:
            bytes: WAV 格式的音频数据
        """
        with self._lock:
            # 从环形缓冲区中按正确顺序取出数据
            # write_pos 之后的数据是最旧的，write_pos 之前的数据是最新的
            ordered = np.concatenate([
                self._buffer[self._write_pos:],
                self._buffer[:self._write_pos]
            ])

        # 去掉开头可能存在的静音部分（缓冲区未满时的零值区域）
        # 找到第一个非零值的位置
        nonzero_indices = np.nonzero(ordered)[0]
        if len(nonzero_indices) == 0:
            # 缓冲区完全为空
            return b""

        ordered = ordered[nonzero_indices[0]:]

        # 转换为 16-bit PCM
        pcm_data = (ordered * 32767).astype(np.int16)

        # 写入内存中的 WAV 文件
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit = 2 bytes
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm_data.tobytes())

        return wav_buffer.getvalue()
