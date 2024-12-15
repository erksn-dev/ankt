import sqlite3
import streamlit as st
import pandas as pd
import plotly.express as px

# Veritabanı bağlantısı
def get_connection():
    return sqlite3.connect("survey.db")

# Kullanıcı doğrulama
def authenticate_user(username, password):
    valid_users = {
        "admin": "1",  # Kullanıcı adı: Şifre
        "user": "1234"
    }
    return valid_users.get(username) == password

# Toplam katılımcı sayısını alma
@st.cache_data
def get_total_participants():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT participant_id) FROM SurveyResponses")
    total = cursor.fetchone()[0]
    conn.close()
    return total

# Soru bazında yanıtları alma
@st.cache_data
def get_question_responses():
    conn = get_connection()
    query = """
        SELECT 
            q.question_text, 
            r.response, 
            COUNT(r.response) as count,
            d.name as department
        FROM SurveyResponses r
        JOIN SurveyQuestions q ON r.question_id = q.id
        JOIN Departments d ON r.department_id = d.id
        GROUP BY q.id, r.response, d.name
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# Departmanları yükleme
@st.cache_data
def load_departments():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM Departments")
    departments = cursor.fetchall()
    conn.close()
    return departments

# Soruları yükleme
@st.cache_data
def load_questions():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, question_text FROM SurveyQuestions")
    questions = cursor.fetchall()
    conn.close()
    return questions

# Streamlit Uygulama Başlatma
st.title("Anket Analiz Ekranı")

# Giriş Ekranı
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("Giriş Yap")
    username = st.text_input("Kullanıcı Adı")
    password = st.text_input("Şifre", type="password")

    if st.button("Giriş"):
        if authenticate_user(username, password):
            st.session_state.logged_in = True
            st.success("Başarıyla giriş yapıldı!")
            st.rerun()
        else:
            st.error("Hatalı kullanıcı adı veya şifre.")
else:
    # Ana Sayfa
    st.sidebar.title("Filtreleme Seçenekleri")
    departments = load_departments()
    department_filter = st.sidebar.selectbox("Departman", ["Hepsi"] + [d[1] for d in departments])

    questions = load_questions()
    question_filter = st.sidebar.selectbox("Soru", ["Hepsi"] + [q[1] for q in questions])

    # Toplam Katılımcı Sayısı
    total_participants = get_total_participants()
    st.markdown(f"### Toplam Katılımcı Sayısı: {total_participants}")

    # Yanıt Analizi
    responses_df = get_question_responses()

    # Departman filtresi uygulama
    if department_filter != "Hepsi":
        responses_df = responses_df[responses_df["department"] == department_filter]

    # Soru filtresi uygulama
    if question_filter != "Hepsi":
        responses_df = responses_df[responses_df["question_text"] == question_filter]

    # Soru bazında yanıt görselleştirme ve tablo
    for question, group in responses_df.groupby("question_text"):
        st.markdown(f"#### **{question}**")

        # Grafik oluşturma
        fig = px.bar(group, x="response", y="count", color="department", text="count",
                     labels={"response": "Yanıt", "count": "Yanıt Sayısı", "department": "Departman"})
        st.plotly_chart(fig, use_container_width=True, key=f"{question}")

        # Tablo oluşturma
        group["percentage"] = group["count"] / group["count"].sum() * 100

        # Genel ortalama hesaplama
        general_average = group.groupby("response").agg({"count": "sum"})
        general_average["percentage"] = general_average["count"] / general_average["count"].sum() * 100
        general_average = general_average.reset_index()
        general_average["department"] = "Genel Ortalama"

        # Genel ortalamayı tabloya ekleme
        combined_group = pd.concat([group, general_average], ignore_index=True)

        st.table(combined_group[["department", "response", "count", "percentage"]].rename(
            columns={"department": "Departman", "response": "Yanıt", "count": "Yanıt Sayısı", "percentage": "%"}))
