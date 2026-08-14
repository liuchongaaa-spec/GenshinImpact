"""Rolling stereo capture: system loopback on the left, microphone on the right."""

from __future__ import annotations

import io
import threading
import wave

import numpy as np
import soundcard as sc


class AudioCapture:
    """Capture two mono sources into one bounded stereo WAV snapshot."""

    def __init__(
        self,
        buffer_seconds: int = 45,
        sample_rate: int = 16000,
        *,
        audio_backend=sc,
        retry_delays: tuple[float, ...] = (1.0, 2.0, 5.0),
    ) -> None:
        if buffer_seconds <= 0 or sample_rate <= 0:
            raise ValueError("buffer_seconds and sample_rate must be positive")
        if not retry_delays or any(delay < 0 for delay in retry_delays):
            raise ValueError("retry_delays must contain non-negative values")

        self.sample_rate = sample_rate
        self.buffer_seconds = buffer_seconds
        self.channels = 2
        self._audio_backend = audio_backend
        self._retry_delays = retry_delays
        self._buffer_size = self.sample_rate * self.buffer_seconds

        self._buffer_sys = np.zeros(self._buffer_size, dtype=np.float32)
        self._buffer_mic = np.zeros(self._buffer_size, dtype=np.float32)
        self._write_pos_sys = 0
        self._write_pos_mic = 0
        self._valid_frames_sys = 0
        self._valid_frames_mic = 0

        self._lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._running = False
        self._thread_sys: threading.Thread | None = None
        self._thread_mic: threading.Thread | None = None

    def start(self) -> None:
        with self._lifecycle_lock:
            if self._running:
                return
            if not self._threads_stopped():
                raise RuntimeError("Previous audio capture threads are still stopping")

            self._stop_event.clear()
            self._running = True
            self._thread_sys = threading.Thread(
                target=self._record_channel_loop,
                args=("system",),
                daemon=True,
            name="desktop-companion-audio-system",
            )
            self._thread_mic = threading.Thread(
                target=self._record_channel_loop,
                args=("microphone",),
                daemon=True,
            name="desktop-companion-audio-microphone",
            )
            self._thread_sys.start()
            self._thread_mic.start()

        print(f"双轨音频缓冲区已启动 (保留最近 {self.buffer_seconds} 秒立体声)")

    def stop(self) -> bool:
        with self._lifecycle_lock:
            if not self._running:
                return self._threads_stopped()

            self._running = False
            self._stop_event.set()
            for thread in (self._thread_sys, self._thread_mic):
                if thread is not None and thread is not threading.current_thread():
                    thread.join(timeout=2.0)
            return self._threads_stopped()

    def _threads_stopped(self) -> bool:
        return all(
            thread is None or not thread.is_alive()
            for thread in (self._thread_sys, self._thread_mic)
        )

    def _record_channel_loop(self, channel: str) -> None:
        consecutive_failures = 0
        chunk_frames = max(1, self.sample_rate // 10)

        while not self._stop_event.is_set():
            try:
                source = self._resolve_source(channel)
                with source.recorder(
                    samplerate=self.sample_rate,
                    channels=[0],
                ) as recorder:
                    consecutive_failures = 0
                    while not self._stop_event.is_set():
                        data = recorder.record(numframes=chunk_frames)
                        mono = data[:, 0] if data.ndim > 1 else data
                        self._write_samples(channel, mono)
            except Exception:
                if self._stop_event.is_set():
                    break
                consecutive_failures += 1
                delay = self._retry_delays[
                    min(consecutive_failures - 1, len(self._retry_delays) - 1)
                ]
                self._stop_event.wait(delay)

    def _resolve_source(self, channel: str):
        if channel == "system":
            speaker = self._audio_backend.default_speaker()
            return self._audio_backend.get_microphone(
                id=str(speaker.name),
                include_loopback=True,
            )
        if channel == "microphone":
            return self._audio_backend.default_microphone()
        raise ValueError(f"Unknown audio channel: {channel}")

    def _write_samples(self, channel: str, samples) -> None:
        mono = np.asarray(samples, dtype=np.float32).reshape(-1)
        if mono.size == 0:
            return
        if mono.size >= self._buffer_size:
            mono = mono[-self._buffer_size:]

        with self._lock:
            if channel == "system":
                buffer = self._buffer_sys
                position = self._write_pos_sys
                valid_frames = self._valid_frames_sys
            elif channel == "microphone":
                buffer = self._buffer_mic
                position = self._write_pos_mic
                valid_frames = self._valid_frames_mic
            else:
                raise ValueError(f"Unknown audio channel: {channel}")

            count = mono.size
            first = min(count, self._buffer_size - position)
            buffer[position:position + first] = mono[:first]
            remaining = count - first
            if remaining:
                buffer[:remaining] = mono[first:]

            position = (position + count) % self._buffer_size
            valid_frames = min(self._buffer_size, valid_frames + count)
            if channel == "system":
                self._write_pos_sys = position
                self._valid_frames_sys = valid_frames
            else:
                self._write_pos_mic = position
                self._valid_frames_mic = valid_frames

    def get_audio_bytes(self) -> bytes:
        with self._lock:
            system = self._ordered_valid(
                self._buffer_sys.copy(),
                self._write_pos_sys,
                self._valid_frames_sys,
            )
            microphone = self._ordered_valid(
                self._buffer_mic.copy(),
                self._write_pos_mic,
                self._valid_frames_mic,
            )

        frame_count = max(system.size, microphone.size)
        if frame_count == 0:
            return b""

        system = self._left_pad(system, frame_count)
        microphone = self._left_pad(microphone, frame_count)
        active = np.flatnonzero((system != 0) | (microphone != 0))
        if active.size == 0:
            return b""

        first_active = int(active[0])
        stereo = np.column_stack((system[first_active:], microphone[first_active:]))
        pcm_data = (np.clip(stereo, -1.0, 1.0) * 32767).astype(np.int16)

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(pcm_data.tobytes())
        return wav_buffer.getvalue()

    @staticmethod
    def _ordered_valid(
        buffer: np.ndarray,
        write_position: int,
        valid_frames: int,
    ) -> np.ndarray:
        if valid_frames <= 0:
            return np.empty(0, dtype=np.float32)
        valid_frames = min(valid_frames, buffer.size)
        start = (write_position - valid_frames) % buffer.size
        end = start + valid_frames
        if end <= buffer.size:
            return buffer[start:end]
        return np.concatenate((buffer[start:], buffer[:end - buffer.size]))

    @staticmethod
    def _left_pad(samples: np.ndarray, frame_count: int) -> np.ndarray:
        if samples.size == frame_count:
            return samples
        result = np.zeros(frame_count, dtype=np.float32)
        if samples.size:
            result[-samples.size:] = samples
        return result
