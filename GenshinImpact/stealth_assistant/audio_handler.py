# -*- coding: utf-8 -*-
"""
音频处理模块 - 录音、设备管理、音量计算
"""
import numpy as np
import soundcard as sc
import soundfile as sf
import os
from config import AUDIO_SAMPLE_RATE, AUDIO_CHUNK_FRAMES


class AudioHandler:
    """音频处理器"""
    
    def __init__(self):
        """初始化音频处理器"""
        self.devices = []
        self.current_device = None
        self.is_recording = False
        self.audio_buffer = []
        
    def get_devices(self) -> list:
        """
        获取所有可用的音频输入设备
        
        Returns:
            list: 设备列表，每项为 (index, name, is_loopback)
        """
        try:
            devices = sc.all_microphones(include_loopback=True)
            self.devices = devices
            
            result = []
            for i, dev in enumerate(devices):
                name = dev.name
                is_loopback = "Monitor" in name or "Stereo Mix" in name or "Loopback" in name
                result.append((i, name, is_loopback))
                
            return result
        except Exception as e:
            print(f"获取设备失败: {e}")
            return []
            
    def set_device(self, index: int) -> bool:
        """
        设置当前录音设备
        
        Args:
            index: 设备索引
            
        Returns:
            bool: 是否成功
        """
        if 0 <= index < len(self.devices):
            self.current_device = self.devices[index]
            return True
        return False
        
    def start_recording(self, volume_callback=None):
        """
        开始录音
        
        Args:
            volume_callback: 音量回调函数，接收音量值(0-1)
            
        Yields:
            numpy.ndarray: 音频数据块
        """
        if self.current_device is None:
            raise ValueError("No device selected")
            
        self.is_recording = True
        self.audio_buffer = []
        
        with self.current_device.recorder(samplerate=AUDIO_SAMPLE_RATE) as mic:
            while self.is_recording:
                data = mic.record(numframes=AUDIO_CHUNK_FRAMES)
                self.audio_buffer.append(data)
                
                # 计算并回调音量
                if volume_callback:
                    volume = self.calculate_volume(data)
                    volume_callback(volume)
                    
                yield data
                
    def stop_recording(self):
        """停止录音"""
        self.is_recording = False
        
    def get_recorded_audio(self) -> np.ndarray:
        """
        获取录制的完整音频
        
        Returns:
            numpy.ndarray: 完整音频数据
        """
        if not self.audio_buffer:
            return None
        return np.concatenate(self.audio_buffer, axis=0)
        
    def save_audio(self, filepath: str) -> bool:
        """
        保存录制的音频到文件
        
        Args:
            filepath: 文件路径
            
        Returns:
            bool: 是否成功
        """
        audio = self.get_recorded_audio()
        if audio is None:
            return False
            
        try:
            # 只取第一个声道
            sf.write(filepath, audio[:, :1], AUDIO_SAMPLE_RATE)
            return True
        except Exception as e:
            print(f"保存音频失败: {e}")
            return False
            
    def is_silent(self, threshold: float = 0.01) -> bool:
        """
        检测录制的音频是否为静音
        
        Args:
            threshold: 静音阈值
            
        Returns:
            bool: 是否静音
        """
        audio = self.get_recorded_audio()
        if audio is None:
            return True
        return np.max(np.abs(audio)) < threshold
        
    @staticmethod
    def calculate_volume(audio_data: np.ndarray) -> float:
        """
        计算音频数据的音量级别
        
        Args:
            audio_data: 音频数据
            
        Returns:
            float: 音量级别 (0-1)
        """
        if audio_data is None or len(audio_data) == 0:
            return 0.0
            
        # 计算RMS (均方根)
        rms = np.sqrt(np.mean(audio_data ** 2))
        
        # 归一化到0-1范围 (假设最大RMS约为0.5)
        normalized = min(1.0, rms * 2)
        
        return normalized
        
    def clear_buffer(self):
        """清空音频缓冲区"""
        self.audio_buffer = []
        
    @staticmethod
    def cleanup_temp_file(filepath: str):
        """
        清理临时音频文件
        
        Args:
            filepath: 文件路径
        """
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass
