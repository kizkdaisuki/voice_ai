#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语音识别助手
支持麦克风、系统音频、混合音频的实时语音识别
支持中文和英文识别
"""

import os
import sys
import time
import threading
import queue
import wave
import tempfile
from typing import Optional, List
import argparse

try:
    import speech_recognition as sr
    import pyaudio
    import soundcard as sc
    import numpy as np
except ImportError as e:
    print(f"❌ 缺少依赖包: {e}")
    print("请运行: pip install -r requirements.txt")
    sys.exit(1)


class VoiceRecognizer:
    """语音识别器"""
    
    def __init__(self, language="zh-CN"):
        """
        初始化语音识别器
        Args:
            language: 识别语言 ("zh-CN" 中文, "en-US" 英文, "auto" 自动检测)
        """
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.language = language
        self.is_running = False
        self.audio_queue = queue.Queue()
        
        # 调整识别器设置
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.5
        
        print("🎤 语音识别器初始化完成")
        self._calibrate_microphone()
    
    def _calibrate_microphone(self):
        """校准麦克风"""
        print("🔧 正在校准麦克风环境噪音...")
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
        print(f"✅ 校准完成，噪音阈值: {self.recognizer.energy_threshold}")
    
    def recognize_audio(self, audio_data) -> Optional[str]:
        """识别音频数据"""
        try:
            if self.language == "auto":
                # 尝试中文识别
                try:
                    text_cn = self.recognizer.recognize_google(audio_data, language="zh-CN")
                    return f"[中文] {text_cn}"
                except:
                    pass
                
                # 尝试英文识别
                try:
                    text_en = self.recognizer.recognize_google(audio_data, language="en-US")
                    return f"[英文] {text_en}"
                except:
                    pass
                
                return None
            else:
                # 指定语言识别
                text = self.recognizer.recognize_google(audio_data, language=self.language)
                lang_name = "中文" if self.language == "zh-CN" else "英文"
                return f"[{lang_name}] {text}"
                
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            print(f"❌ 识别服务错误: {e}")
            return None
        except Exception as e:
            print(f"❌ 识别错误: {e}")
            return None


class MicrophoneRecorder:
    """麦克风录音器"""
    
    def __init__(self, recognizer: VoiceRecognizer):
        self.recognizer = recognizer
        self.is_recording = False
    
    def start_recording(self):
        """开始麦克风录音识别"""
        self.is_recording = True
        print("🎙️  开始麦克风录音识别...")
        print("💡 说话时会自动识别，按 Ctrl+C 停止")
        
        def record_callback(recognizer, audio):
            """录音回调函数"""
            threading.Thread(
                target=self._process_audio,
                args=(audio,),
                daemon=True
            ).start()
        
        # 启动后台监听
        stop_listening = self.recognizer.recognizer.listen_in_background(
            self.recognizer.microphone,
            record_callback,
            phrase_time_limit=5
        )
        
        try:
            while self.is_recording:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            stop_listening(wait_for_stop=False)
            self.is_recording = False
            print("\n🛑 麦克风录音已停止")
    
    def _process_audio(self, audio):
        """处理音频数据"""
        text = self.recognizer.recognize_audio(audio)
        if text:
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] 🎤 {text}")


class SystemAudioRecorder:
    """系统音频录音器"""
    
    def __init__(self, recognizer: VoiceRecognizer):
        self.recognizer = recognizer
        self.is_recording = False
        self.sample_rate = 16000
        self.chunk_size = 1024
    
    def start_recording(self):
        """开始系统音频录音识别"""
        try:
            # 获取默认扬声器（用于录制系统音频）
            default_speaker = sc.default_speaker()
            print(f"🔊 使用音频设备: {default_speaker.name}")
            
            self.is_recording = True
            print("🖥️  开始系统音频录音识别...")
            print("💡 播放音频时会自动识别，按 Ctrl+C 停止")
            
            with default_speaker.recorder(samplerate=self.sample_rate) as mic:
                audio_buffer = []
                buffer_duration = 3  # 3秒缓冲
                buffer_size = int(self.sample_rate * buffer_duration)
                
                try:
                    while self.is_recording:
                        # 录制一小段音频
                        data = mic.record(numframes=self.chunk_size)
                        audio_buffer.extend(data[:, 0])  # 取单声道
                        
                        # 当缓冲区满时处理音频
                        if len(audio_buffer) >= buffer_size:
                            self._process_system_audio(
                                np.array(audio_buffer, dtype=np.float32)
                            )
                            audio_buffer = []
                        
                        time.sleep(0.01)
                        
                except KeyboardInterrupt:
                    pass
                
        except Exception as e:
            print(f"❌ 系统音频录制错误: {e}")
            print("💡 提示: 在 macOS 上可能需要授权应用访问音频设备")
        finally:
            self.is_recording = False
            print("\n🛑 系统音频录音已停止")
    
    def _process_system_audio(self, audio_data):
        """处理系统音频数据"""
        try:
            # 检查音频是否有内容（避免静音时的识别）
            if np.max(np.abs(audio_data)) < 0.01:
                return
            
            # 转换为speech_recognition可用的格式
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                # 保存为WAV文件
                with wave.open(temp_file.name, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(self.sample_rate)
                    
                    # 转换为16位整数
                    audio_int16 = (audio_data * 32767).astype(np.int16)
                    wav_file.writeframes(audio_int16.tobytes())
                
                # 使用speech_recognition识别
                with sr.AudioFile(temp_file.name) as source:
                    audio = self.recognizer.recognizer.record(source)
                    text = self.recognizer.recognize_audio(audio)
                    
                    if text:
                        timestamp = time.strftime("%H:%M:%S")
                        print(f"[{timestamp}] 🔊 {text}")
                
                # 清理临时文件
                os.unlink(temp_file.name)
                
        except Exception as e:
            # 静默处理错误，避免过多错误输出
            pass


class MixedAudioRecorder:
    """混合音频录音器（麦克风+系统音频）"""
    
    def __init__(self, recognizer: VoiceRecognizer):
        self.recognizer = recognizer
        self.is_recording = False
        self.mic_recorder = MicrophoneRecorder(recognizer)
        self.sys_recorder = SystemAudioRecorder(recognizer)
    
    def start_recording(self):
        """开始混合音频录音识别"""
        self.is_recording = True
        print("🎵 开始混合音频录音识别（麦克风 + 系统音频）...")
        print("💡 同时识别麦克风和系统音频，按 Ctrl+C 停止")
        
        # 启动麦克风录音线程
        mic_thread = threading.Thread(
            target=self._start_microphone,
            daemon=True
        )
        
        # 启动系统音频录音线程
        sys_thread = threading.Thread(
            target=self._start_system_audio,
            daemon=True
        )
        
        mic_thread.start()
        sys_thread.start()
        
        try:
            while self.is_recording:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            self.is_recording = False
            self.mic_recorder.is_recording = False
            self.sys_recorder.is_recording = False
            print("\n🛑 混合音频录音已停止")
    
    def _start_microphone(self):
        """启动麦克风录音"""
        self.mic_recorder.is_recording = True
        
        def record_callback(recognizer, audio):
            threading.Thread(
                target=self._process_mic_audio,
                args=(audio,),
                daemon=True
            ).start()
        
        stop_listening = self.recognizer.recognizer.listen_in_background(
            self.recognizer.microphone,
            record_callback,
            phrase_time_limit=5
        )
        
        while self.is_recording:
            time.sleep(0.1)
        
        stop_listening(wait_for_stop=False)
    
    def _start_system_audio(self):
        """启动系统音频录音"""
        self.sys_recorder.is_recording = True
        try:
            default_speaker = sc.default_speaker()
            
            with default_speaker.recorder(samplerate=16000) as mic:
                audio_buffer = []
                buffer_size = int(16000 * 3)  # 3秒缓冲
                
                while self.is_recording:
                    data = mic.record(numframes=1024)
                    audio_buffer.extend(data[:, 0])
                    
                    if len(audio_buffer) >= buffer_size:
                        self._process_sys_audio(
                            np.array(audio_buffer, dtype=np.float32)
                        )
                        audio_buffer = []
                    
                    time.sleep(0.01)
                    
        except Exception as e:
            if self.is_recording:  # 只在还在录音时显示错误
                print(f"❌ 系统音频线程错误: {e}")
    
    def _process_mic_audio(self, audio):
        """处理麦克风音频"""
        text = self.recognizer.recognize_audio(audio)
        if text:
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] 🎤 {text}")
    
    def _process_sys_audio(self, audio_data):
        """处理系统音频"""
        try:
            if np.max(np.abs(audio_data)) < 0.01:
                return
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                with wave.open(temp_file.name, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(16000)
                    
                    audio_int16 = (audio_data * 32767).astype(np.int16)
                    wav_file.writeframes(audio_int16.tobytes())
                
                with sr.AudioFile(temp_file.name) as source:
                    audio = self.recognizer.recognizer.record(source)
                    text = self.recognizer.recognize_audio(audio)
                    
                    if text:
                        timestamp = time.strftime("%H:%M:%S")
                        print(f"[{timestamp}] 🔊 {text}")
                
                os.unlink(temp_file.name)
                
        except Exception:
            pass


def show_menu():
    """显示菜单"""
    print("\n" + "="*50)
    print("🎤 语音识别助手")
    print("="*50)
    print("1. 麦克风识别")
    print("2. 系统音频识别")
    print("3. 混合音频识别（麦克风 + 系统音频）")
    print("4. 设置")
    print("5. 退出")
    print("="*50)


def show_settings(recognizer):
    """显示设置菜单"""
    while True:
        print("\n" + "="*30)
        print("⚙️  设置")
        print("="*30)
        print(f"当前语言: {recognizer.language}")
        print("1. 设置为中文 (zh-CN)")
        print("2. 设置为英文 (en-US)")
        print("3. 设置为自动检测 (auto)")
        print("4. 返回主菜单")
        print("="*30)
        
        choice = input("请选择: ").strip()
        
        if choice == "1":
            recognizer.language = "zh-CN"
            print("✅ 已设置为中文识别")
        elif choice == "2":
            recognizer.language = "en-US"
            print("✅ 已设置为英文识别")
        elif choice == "3":
            recognizer.language = "auto"
            print("✅ 已设置为自动检测")
        elif choice == "4":
            break
        else:
            print("❌ 无效选择")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="语音识别助手")
    parser.add_argument(
        "--language", "-l",
        choices=["zh-CN", "en-US", "auto"],
        default="zh-CN",
        help="识别语言 (默认: zh-CN)"
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["mic", "system", "mixed"],
        help="直接启动模式"
    )
    
    args = parser.parse_args()
    
    print("🚀 正在启动语音识别助手...")
    
    # 初始化识别器
    recognizer = VoiceRecognizer(language=args.language)
    
    # 如果指定了模式，直接启动
    if args.mode:
        if args.mode == "mic":
            recorder = MicrophoneRecorder(recognizer)
            recorder.start_recording()
        elif args.mode == "system":
            recorder = SystemAudioRecorder(recognizer)
            recorder.start_recording()
        elif args.mode == "mixed":
            recorder = MixedAudioRecorder(recognizer)
            recorder.start_recording()
        return
    
    # 交互式菜单
    while True:
        show_menu()
        choice = input("请选择 (1-5): ").strip()
        
        if choice == "1":
            recorder = MicrophoneRecorder(recognizer)
            recorder.start_recording()
        elif choice == "2":
            recorder = SystemAudioRecorder(recognizer)
            recorder.start_recording()
        elif choice == "3":
            recorder = MixedAudioRecorder(recognizer)
            recorder.start_recording()
        elif choice == "4":
            show_settings(recognizer)
        elif choice == "5":
            print("👋 再见！")
            break
        else:
            print("❌ 无效选择，请重新输入")


if __name__ == "__main__":
    main() 