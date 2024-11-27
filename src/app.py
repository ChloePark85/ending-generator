import streamlit as st
import requests
import logging
import wave
import io
import os
import tempfile
from pydub import AudioSegment
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 설정값 불러오기
TTS_API_ENDPOINT = os.getenv('TTS_API_ENDPOINT')
TTS_VOICE_ID = os.getenv('TTS_VOICE_ID')

if not TTS_API_ENDPOINT or not TTS_VOICE_ID:
    raise ValueError("TTS API 설정이 필요합니다. .env 파일을 확인해주세요.")

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

def generate_ending_credit(title, author, narrator):
    """엔딩 크레딧 텍스트를 생성하는 함수"""
    return f"지금까지 {title} 이었습니다. {author}{get_josa(author)} 쓰고 {narrator}{get_josa(narrator)} 읽었으며, 이어가다에서 출판했습니다."

def text_to_speech(text, speed=1.0):
    """TTS API를 호출하여 음성을 생성하는 함수"""
    try:
        payload = {
            "mode": "openfont",
            "sentences": [
                {
                    "type": "text",
                    "text": text,
                    "version": "0",
                    "voice_id": TTS_VOICE_ID,
                    "options": {
                        "speed": speed
                    }
                }
            ]
        }
        
        logging.info("Sending TTS request")
        response = requests.post(
            TTS_API_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            temp_file.write(response.content)
            temp_file.close()
            return temp_file.name
        else:
            st.error(f"TTS API 오류: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        st.error(f"TTS 변환 중 오류가 발생했습니다: {str(e)}")
        return None

def process_audio_files(tts_path, outro_path):
    """TTS 음성과 아웃트로 파일을 처리하고 결합하는 함수"""
    try:
        # 오디오 파일 불러오기 (둘 다 WAV 형식)
        tts_audio = AudioSegment.from_wav(tts_path)
        outro_audio = AudioSegment.from_wav(outro_path)
        
        # 0.5초 공백 추가
        silence = AudioSegment.silent(duration=500)
        
        # 오디오 순차적으로 결합
        combined = tts_audio + silence + outro_audio
        
        # 결합된 오디오를 임시 파일로 저장
        output_path = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3').name
        combined.export(output_path, format='mp3')
        
        return output_path
    except Exception as e:
        st.error(f"오디오 처리 중 오류가 발생했습니다: {str(e)}")
        return None


def main():
    st.title("📚 이어가다 오디오북 엔딩 크레딧 생성기")
    
    # 아웃트로 파일 경로 설정
    outro_path = "assets/ending.wav"
    
    if not os.path.exists(outro_path):
        st.error("엔딩 크레딧 음악 파일을 찾을 수 없습니다.")
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
            
            # TTS 변환 (WAV 파일로 저장)
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

if __name__ == "__main__":
    main()