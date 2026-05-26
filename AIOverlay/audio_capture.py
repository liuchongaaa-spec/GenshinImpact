# -*- coding: utf-8 -*-
"""
音频捕获模块 - 立体声双轨并联录制
左声道：系统扬声器回环（面试官）
右声道：系统默认麦克风（候选人）
全程不写磁盘，按需截取最近 N 秒合成双通道 WAV 数据。
"""

import io
import wave
import threading
import numpy as np
import soundcard as sc


class AudioCapture:
    """系统音频与麦克风双轨滚动缓冲区"""

    def __init__(self, buffer_seconds: int = 45, sample_rate: int = 16000):
        """
        初始化双轨音频捕获器

        Args:
            buffer_seconds: 缓冲区保留的秒数
            sample_rate: 采样率 (Hz)
        """
        self.sample_rate = sample_rate
        self.buffer_seconds = buffer_seconds
        self.channels = 2  # 强制立体声 (Left=Sys, Right=Mic)

        # 环形缓冲区大小
        self._buffer_size = self.sample_rate * self.buffer_seconds
        
        # 面试官 (系统回环)
        self._buffer_sys = np.zeros(self._buffer_size, dtype=np.float32)
        self._write_pos_sys = 0
        
        # 候选人 (麦克风)
        self._buffer_mic = np.zeros(self._buffer_size, dtype=np.float32)
        self._write_pos_mic = 0

        self._lock = threading.Lock()

        # 录音线程控制
        self._running = False
        self._thread_sys = None
        self._thread_mic = None

    def start(self):
        """启动后台双轨录音线程"""
        if self._running:
            return

        self._running = True
        self._thread_sys = threading.Thread(target=self._record_sys_loop, daemon=True)
        self._thread_mic = threading.Thread(target=self._record_mic_loop, daemon=True)
        
        self._thread_sys.start()
        self._thread_mic.start()
        print(f"🎤 双轨音频缓冲区已启动 (保留最近 {self.buffer_seconds} 秒立体声)")

    def stop(self):
        """停止录音"""
        self._running = False
        if self._thread_sys:
            self._thread_sys.join(timeout=2)
        if self._thread_mic:
            self._thread_mic.join(timeout=2)

    def _record_sys_loop(self):
        """系统回环录音循环 (面试官)"""
        try:
            speaker = sc.default_speaker()
            loopback = sc.get_microphone(id=str(speaker.name), include_loopback=True)

            chunk_frames = self.sample_rate // 10

            with loopback.recorder(samplerate=self.sample_rate, channels=[0]) as recorder:
                while self._running:
                    data = recorder.record(numframes=chunk_frames)
                    mono = data[:, 0] if data.ndim > 1 else data

                    with self._lock:
                        n = len(mono)
                        end_pos = self._write_pos_sys + n

                        if end_pos <= self._buffer_size:
                            self._buffer_sys[self._write_pos_sys:end_pos] = mono
                        else:
                            first_part = self._buffer_size - self._write_pos_sys
                            self._buffer_sys[self._write_pos_sys:] = mono[:first_part]
                            self._buffer_sys[:n - first_part] = mono[first_part:]

                        self._write_pos_sys = end_pos % self._buffer_size

        except Exception as e:
            print(f"系统音频捕获异常 (面试官声道静默): {e}")

    def _record_mic_loop(self):
        """麦克风录音循环 (候选人)"""
        try:
            mic = sc.default_microphone()
            chunk_frames = self.sample_rate // 10

            with mic.recorder(samplerate=self.sample_rate, channels=[0]) as recorder:
                while self._running:
                    data = recorder.record(numframes=chunk_frames)
                    mono = data[:, 0] if data.ndim > 1 else data

                    with self._lock:
                        n = len(mono)
                        end_pos = self._write_pos_mic + n

                        if end_pos <= self._buffer_size:
                            self._buffer_mic[self._write_pos_mic:end_pos] = mono
                        else:
                            first_part = self._buffer_size - self._write_pos_mic
                            self._buffer_mic[self._write_pos_mic:] = mono[:first_part]
                            self._buffer_mic[:n - first_part] = mono[first_part:]

                        self._write_pos_mic = end_pos % self._buffer_size

        except Exception as e:
            print(f"麦克风捕获异常 (候选人声道静默，可能未授权或未连接): {e}")

    def get_audio_bytes(self) -> bytes:
        """
        合成双声道并导出为 WAV 字节流
        左声道：系统音频，右声道：麦克风音频
        """
        with self._lock:
            # 展开环形缓冲区
            ordered_sys = np.concatenate([
                self._buffer_sys[self._write_pos_sys:],
                self._buffer_sys[:self._write_pos_sys]
            ])
            ordered_mic = np.concatenate([
                self._buffer_mic[self._write_pos_mic:],
                self._buffer_mic[:self._write_pos_mic]
            ])

        # 寻找静音截断点 (找到各自最早的非零点)
        nonzero_sys = np.nonzero(ordered_sys)[0]
        nonzero_mic = np.nonzero(ordered_mic)[0]

        start_idx = self._buffer_size
        if len(nonzero_sys) > 0:
            start_idx = min(start_idx, nonzero_sys[0])
        if len(nonzero_mic) > 0:
            start_idx = min(start_idx, nonzero_mic[0])

        if start_idx == self._buffer_size:
            return b""  # 两边全是静音

        final_sys = ordered_sys[start_idx:]
        final_mic = ordered_mic[start_idx:]

        # 拼成双声道 [frames, 2]
        stereo = np.column_stack((final_sys, final_mic))

        # 转换为 16-bit PCM
        pcm_data = (stereo * 32767).astype(np.int16)

        # 写入内存中的 WAV 文件
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm_data.tobytes())

        return wav_buffer.getvalue()
