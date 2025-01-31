import sqlite3
import streamlit as st
import json
import uuid  # Benzersiz participant_id oluşturmak içi
from github import Github
import base64
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_NAME = "erksn-dev/ankt"
FILE_PATH = "survey.db"
GITHUB_PATH = "backup/survey.db"
hide_streamlit_style = """
    <style>
        .block-container { padding-top: 0rem; padding-bottom: 0rem; margin-top: 0rem; }
        div[data-testid="stToolbar"], div[data-testid="stDecoration"], div[data-testid="stStatusWidget"],
        #MainMenu, header, footer { visibility: hidden; height: 0%; position: fixed; }
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)
def upload_db_to_github():
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(REPO_NAME)
        with open(FILE_PATH, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        repo.create_file(
            path=GITHUB_PATH,
            message="Otomatik veritabanı yedekleme",
            content=content,
            branch="main"
        )
        st.success("Veritabanı GitHub'a yüklendi!")
    except Exception as e:
        st.error(f"Hata oluştu: {e}")

# Uygulama başladığında yedekleme yap
upload_db_to_github()

# Veritabanı bağlantı fonksiyonu
def get_connection():
    return sqlite3.connect("survey.db")

# Departmanları yükleme fonksiyonu
def load_departments():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM Departments")
    departments = cursor.fetchall()
    conn.close()
    return departments

# Soruları yükleme fonksiyonu
def load_questions():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, question_text, type FROM SurveyQuestions")
    questions = cursor.fetchall()
    conn.close()
    return questions

# Cevapları kaydetme fonksiyonu
def save_responses(department_id, responses):
    conn = get_connection()
    cursor = conn.cursor()
    participant_id = str(uuid.uuid4())  # Benzersiz participant_id oluştur
    for question_id, response in responses.items():
        if isinstance(response, dict):  # Eğer yanıt bir sözlük ise (sıralama soruları için)
            response = json.dumps(response)  # JSON formatına dönüştür
        cursor.execute(
            "INSERT INTO SurveyResponses (participant_id, department_id, question_id, response) VALUES (?, ?, ?, ?)",
            (participant_id, department_id, question_id, response),
        )
    conn.commit()
    conn.close()

# Katılımcı sayısını hesaplama fonksiyonu
def get_total_participants():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT participant_id) FROM SurveyResponses")
    total = cursor.fetchone()[0]
    conn.close()
    return total
# Streamlit başlık ve açıklama
st.title("Çalışan Memnuniyeti Anketi")

# Sayfa durumu için bir durum tutucu
if "stage" not in st.session_state:
    st.session_state.stage = "department_selection"

if st.session_state.stage == "department_selection":
    st.write("Lütfen departmanınızı seçiniz ve ardından İleri butonuna basınız.")

    # Departman seçimi
    departments = load_departments()
    department_names = [dep[1] for dep in departments]
    selected_department = st.selectbox("Departmanınızı seçiniz:", department_names, key="department_select")

    if st.button("İleri", key="next_department"):
        for dep in departments:
            if dep[1] == selected_department:
                st.session_state.department_id = dep[0]
                break
        st.session_state.stage = "questions"
        st.rerun()

elif st.session_state.stage == "questions":
    # Soruları yükle
    questions = load_questions()

    if "current_question" not in st.session_state:
        st.session_state.current_question = 0

    responses = st.session_state.get("responses", {})

    # Soru Gösterimi
    if st.session_state.current_question < len(questions):
        q_id, q_text, q_type = questions[st.session_state.current_question]

        if q_type == "çoktan seçmeli":
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT choice_text FROM Choices WHERE question_id = ?", (q_id,))
            choices = [row[0] for row in cursor.fetchall()]
            conn.close()

            st.markdown(f"<h3 style='font-size: 24px;'>{q_text}</h3>", unsafe_allow_html=True)
            responses[q_id] = st.radio("", choices, key=f"question_{q_id}", label_visibility="collapsed")

            st.session_state.responses = responses

            col1, col2 = st.columns(2)
            with col1:
                if st.button("⬅ Geri", key="prev_question", use_container_width=True):
                    if st.session_state.current_question > 0:
                        st.session_state.current_question -= 1
                        st.rerun()
            with col2:
                if st.button("İleri ➡", key="next_question", use_container_width=True):
                    st.session_state.current_question += 1
                    st.rerun()

        elif q_type == "sıralama":
            st.markdown(f"<h3 style='font-size: 24px;'>{q_text}</h3>", unsafe_allow_html=True)
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT choice_text FROM Choices WHERE question_id = ?", (q_id,))
            choices = [row[0] for row in cursor.fetchall()]
            conn.close()

            order_responses = {}
            duplicate_error = False
            used_ranks = set()

            for choice in choices:
                rank = st.number_input(
                    f"{choice}",  # Burada sadece seçenek metni gösteriliyor
                    min_value=1,
                    max_value=len(choices),
                    key=f"ranking_{q_id}_{choice}",

                )
                if rank in used_ranks:
                    duplicate_error = True
                used_ranks.add(rank)
                order_responses[choice] = rank

            responses[q_id] = {choice: rank for choice, rank in order_responses.items()}

            if duplicate_error or len(used_ranks) != len(choices):
                st.error("Her seçenek için farklı ve benzersiz bir sıra numarası girmelisiniz.")
            else:
                st.session_state.responses = responses

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("⬅ Geri", key="prev_question", use_container_width=True):
                        if st.session_state.current_question > 0:
                            st.session_state.current_question -= 1
                            st.rerun()
                with col2:
                    if st.button("İleri ➡", key="next_question", use_container_width=True):
                        st.session_state.current_question += 1
                        st.rerun()
        else:
            st.markdown(f"<h3 style='font-size: 24px;'>{q_text}</h3>", unsafe_allow_html=True)
            responses[q_id] = st.text_input("", key=f"question_{q_id}", label_visibility="collapsed")

            st.session_state.responses = responses

            col1, col2 = st.columns(2)
            with col1:
                if st.button("⬅ Geri", key="prev_question", use_container_width=True):
                    if st.session_state.current_question > 0:
                        st.session_state.current_question -= 1
                        st.rerun()
            with col2:
                if st.button("İleri ➡", key="next_question", use_container_width=True):
                    st.session_state.current_question += 1
                    st.rerun()

    else:
        if st.button("Cevapları Kaydet", key="save_responses", use_container_width=True):
            save_responses(st.session_state.department_id, st.session_state.responses)
            st.session_state.stage = "thank_you"
            st.rerun()

elif st.session_state.stage == "thank_you":
    st.success("Cevaplarınız başarıyla kaydedildi! Anketimize katıldığınız için teşekkür ederiz.")
