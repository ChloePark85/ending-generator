import streamlit as st
import requests
import logging
import wave
import io
import os
import tempfile
from pydub import AudioSegment
from elevenlabs import ElevenLabs
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO)

# Streamlit Secrets에서 TTS 설정 가져오기
try:
    TTS_API_ENDPOINT = st.secrets["TTS_API_ENDPOINT"]
    TTS_VOICE_ID = st.secrets["TTS_VOICE_ID"]
except Exception as e:
    st.error("TTS API 설정이 필요합니다. Streamlit Secrets를 확인해주세요.")
    st.stop()

# Streamlit Secrets에서 Elevenlabs 설정 가져오기
try:
    ELEVENLABS_API_KEY = st.secrets["ELEVENLABS_API_KEY"]
except Exception as e:
    st.error("Elevenlabs API 키가 필요합니다. Streamlit Secrets를 확인해주세요.")
    st.stop()

# 고정된 아웃트로 URL
OUTRO_URL = "https://nadio-studio-open-fonts-metadata.s3.ap-northeast-2.amazonaws.com/audio/%E1%84%86%E1%85%A1%E1%84%8C%E1%85%B5%E1%84%86%E1%85%A1%E1%86%A8+%E1%84%8C%E1%85%B5%E1%86%BC%E1%84%80%E1%85%B3%E1%86%AF_nadio.wav"

def download_outro():
    """S3에서 아웃트로 음악 다운로드"""
    try:
        response = requests.get(OUTRO_URL)
        if response.status_code == 200:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            temp_file.write(response.content)
            temp_file.close()
            return temp_file.name
        else:
            st.error(f"엔딩 음악 다운로드 실패: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"엔딩 음악 다운로드 중 오류 발생: {str(e)}")
        return None

def has_jongsung(text):
    """한글 문자의 받침 유무를 확인하는 함수"""
    if not text:
        return False
    last_char = text[-1]
    if '가' <= last_char <= '힣':
        char_code = ord(last_char) - 0xAC00
        return char_code % 28 != 0
    return False

def get_josa(text, josa_type='이/가'):
    """받침 유무에 따라 적절한 조사를 반환하는 함수"""
    if has_jongsung(text):
        return '이' if josa_type == '이/가' else '을'
    return '가' if josa_type == '이/가' else '를'

def is_korean(text):
    """텍스트가 한글을 포함하는지 확인하는 함수"""
    return any('가' <= char <= '힣' for char in text)

def generate_ending_credit(title, author, narrator):
    """엔딩 크레딧 텍스트를 생성하는 함수"""
    # 타이틀, 작가, 낭독자 중 하나라도 한글이 있는지 확인
    if is_korean(title) or is_korean(author) or is_korean(narrator):
        return f"지금까지 {title} 이었습니다. {author}{get_josa(author)} 쓰고, {narrator}{get_josa(narrator)} 읽었으며, 이어가다에서 출판했습니다."
    else:
        return f"You've been listening to {title}. Written by {author}, read by {narrator}, and published by Ieogada."

def text_to_speech(text, speed=1.0):
    """Elevenlabs TTS API를 호출하여 음성을 생성하는 함수"""
    try:
        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        
        # 음성 생성
        audio_stream = client.text_to_speech.convert(
            voice_id="xtPpJW6BY4c8ATbuVBO1",  # 원하는 voice_id로 변경 가능
            text=text,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128"
        )
        
        # 스트림을 바이트로 변환
        if hasattr(audio_stream, 'read'):
            audio_bytes = audio_stream.read()
        elif isinstance(audio_stream, (bytes, bytearray)):
            audio_bytes = audio_stream
        else:
            audio_bytes = b''.join(chunk for chunk in audio_stream)
        
        # 임시 파일로 저장
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_file.write(audio_bytes)
        temp_file.close()
        
        return temp_file.name
            
    except Exception as e:
        st.error(f"TTS 변환 중 오류가 발생했습니다: {str(e)}")
        return None

def process_audio_files(tts_path, outro_path):
    """TTS 음성과 아웃트로 파일을 처리하고 결합하는 함수"""
    try:
        # 오디오 파일 불러오기
        tts_audio = AudioSegment.from_mp3(tts_path)  # from_wav에서 from_mp3로 변경
        outro_audio = AudioSegment.from_wav(outro_path)
        
        # 0.5초 공백 추가
        silence = AudioSegment.silent(duration=500)
        
        # 오디오 순차적으로 결합
        combined = tts_audio + silence + outro_audio
        
        # 결합된 오디오를 MP3로 저장
        output_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3').name
        combined.export(
            output_path,
            format='mp3',
            bitrate='192k',
            parameters=[
                "-ar", "44100",  # 샘플링 레이트 44.1kHz
                "-ac", "2",      # 스테레오
                "-ab", "192k"    # 오디오 비트레이트
            ]
        )
        
        return output_path
    except Exception as e:
        st.error(f"오디오 처리 중 오류가 발생했습니다: {str(e)}")
        logging.error(f"상세 오류: {str(e)}")  # 디버깅을 위한 로깅 추가
        return None

def main():
    st.title("📚 이어가다 오디오북 엔딩 크레딧 생성기")
    
    # S3에서 아웃트로 음악 다운로드
    with st.spinner("엔딩 음악 준비중..."):
        outro_path = download_outro()
    
    if not outro_path:
        st.error("엔딩 음악을 불러올 수 없습니다.")
        st.stop()
    
    # 입력 폼
    with st.form("ending_credit_form"):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("작품명을 입력하세요")
            author = st.text_input("작가명을 입력하세요")
        with col2:
            narrator = st.text_input("낭독자명을 입력하세요")
            speed = st.slider("음성 속도", min_value=0.5, max_value=2.0, value=1.0, step=0.1)
        
        submitted = st.form_submit_button("엔딩 크레딧 생성", use_container_width=True)
        
    if submitted and title and author and narrator:
        with st.spinner('엔딩 크레딧 생성 중...'):
            # 엔딩 크레딧 텍스트 생성
            credit_text = generate_ending_credit(title, author, narrator)
            st.info("생성된 엔딩 크레딧: " + credit_text)
            
            # TTS 변환
            tts_path = text_to_speech(credit_text, speed)
            
            if tts_path:
                try:
                    # 오디오 파일 처리 및 결합
                    final_path = process_audio_files(tts_path, outro_path)
                    
                    if final_path:
                        # 결합된 오디오 파일 읽기
                        with open(final_path, 'rb') as audio_file:
                            audio_data = audio_file.read()
                        
                        # 오디오 재생
                        st.audio(audio_data, format='audio/mp3')
                        
                        # 다운로드 버튼
                        st.download_button(
                            label="엔딩 크레딧 오디오 다운로드",
                            data=audio_data,
                            file_name=f"ending_credit_{title}.mp3",
                            mime="audio/mp3",
                            use_container_width=True
                        )
                        
                        # 임시 파일들 삭제
                        os.unlink(tts_path)
                        os.unlink(final_path)
                        
                except Exception as e:
                    st.error(f"오디오 처리 중 오류가 발생했습니다: {str(e)}")
    
    # 마지막에 아웃트로 임시 파일 삭제
    if outro_path and os.path.exists(outro_path):
        os.unlink(outro_path)

if __name__ == "__main__":
    main()