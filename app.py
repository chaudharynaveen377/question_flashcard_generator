import streamlit as st
from groq import Groq
import re
import pandas as pd
import json
import base64
# Initialize Groq client
# client = Groq(api_key="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")
client = Groq(api_key="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")

# Page config (unchanged)
st.set_page_config(page_title="Flashcard Generator", page_icon="🧠", layout="centered")

# CSS (unchanged)
st.markdown("""
    <style>
    :root {
        --primary-bg: #f5f7fa;
        --card-bg: #ffffff;
        --text-color: #2c3e50;
        --answer-color: #2980b9;
        --border-color: #e0e0e0;
        --mcq-color: #9b59b6;
        --sa-color: #3498db;
    }
    
    .flashcard {
        background-color: var(--card-bg);
        border-radius: 12px;
        padding: 22px;
        margin: 15px 0;
        box-shadow: 0 6px 12px rgba(0,0,0,0.08);
        border: 1px solid var(--border-color);
        transition: all 0.3s ease;
        color: var(--text-color);
    }
    
    .mcq-card {
        border-left: 4px solid var(--mcq-color);
    }
    
    .sa-card {
        border-left: 4px solid var(--sa-color);
    }
    
    .question {
        font-weight: 600;
        font-size: 1.15em;
        margin-bottom: 12px;
        line-height: 1.4;
    }
    
    .answer {
        margin-top: 15px;
        padding: 12px;
        border-radius: 8px;
        font-size: 1.05em;
        line-height: 1.5;
    }
    
    .sa-answer {
        color: var(--sa-color);
        background-color: rgba(52, 152, 219, 0.1);
    }
    
    .mcq-option {
        margin: 8px 0;
        padding: 8px 12px;
        border-radius: 6px;
        background-color: rgba(155, 89, 182, 0.1);
    }
    
    .mcq-correct {
        background-color: rgba(46, 204, 113, 0.2);
        border-left: 3px solid #2ecc71;
    }
    
    .user-incorrect {
        background-color: rgba(231, 76, 60, 0.2);
        border-left: 3px solid #e74c3c;
    }
    
    .section-header {
        padding-bottom: 8px;
        border-bottom: 2px solid;
        margin: 25px 0 15px 0;
    }
    
    .mcq-header {
        color: var(--mcq-color);
        border-color: var(--mcq-color);
    }
    
    .sa-header {
        color: var(--sa-color);
        border-color: var(--sa-color);
    }
    </style>
""", unsafe_allow_html=True)

# Title (unchanged)
st.title("🧠 Strict Flashcard Generator")
st.markdown("Generate **MCQ** or **Short Answer** questions from your content")

# Input section (unchanged)
# Text or Document Selection
with st.expander("📝 Input Content", expanded=True):
    input_mode = st.radio("Choose input method:", ["Paste Text", "Upload Document (.txt, .pdf)"], horizontal=True)

    text = ""

    if input_mode == "Paste Text":
        text = st.text_area("Enter your educational content:", height=200, placeholder="Paste your study material here...")
    
    elif input_mode == "Upload Document (.txt, .pdf)":
        upload_file = st.file_uploader("Upload a file", type=["txt", "pdf"])
        
        if upload_file is not None:
            if upload_file.type == "text/plain":
                text = upload_file.read().decode("utf-8")
            elif upload_file.type == "application/pdf":
                try:
                    from PyPDF2 import PdfReader
                    reader = PdfReader(upload_file)
                    text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
                except Exception as e:
                    st.error(f"Error reading PDF: {str(e)}")

# Settings sidebar (only added difficulty slider)
# Settings sidebar (enhanced with translation)
with st.sidebar:
    st.header("⚙️ Generation Settings")

    # Difficulty level
    difficulty = st.select_slider("Difficulty Level:", ["Easy", "Medium", "Hard"], value="Medium")

    # Number of questions
    num_questions = st.slider("Number of Questions:", 1, 15, 5)

    # Question type
    question_type = st.radio("Question Type:", ["Multiple Choice (MCQ)", "Short Answer"], index=0)

    if question_type == "Multiple Choice (MCQ)":
        include_explanations = st.checkbox("Include explanations", value=True)

    st.markdown("---")

    # Language translation option
    st.subheader("🌐 Translation Settings")
    enable_translation = st.checkbox("Translate content before generating questions")
    
    target_language = None
    if enable_translation:
        target_language = st.selectbox(
            "Select target language",
            ["Hindi", "Spanish", "French", "German", "Japanese"],
            index=0
        )
 
# Session state (unchanged)
if 'flashcards' not in st.session_state:
    st.session_state.flashcards = []
if 'user_answers' not in st.session_state:
    st.session_state.user_answers = {}

# Updated prompt templates (only added difficulty)
def build_mcq_prompt(user_text, difficulty, count, include_explanations):
    return f"""You are an expert MCQ generator. Your job is to generate exactly {count} high-quality multiple choice questions (MCQs) from the given educational content. Follow these STRICT rules.

CONTENT:
{user_text.strip()}

DIFFICULTY: {difficulty}
- Easy: Focus on simple factual recall.
- Medium: Test conceptual understanding.
- Hard: Assess analytical and application-based thinking.

INSTRUCTIONS:
- Ensure each MCQ has 1 correct answer and 3 distractors (plausible but incorrect options).
- Avoid duplication or vague options.
- Mix up the position of correct answers (A, B, C, D).
- Ensure questions cover a range of topics from the content (compute all meaningful permutations).
- Do not include any extra commentary or metadata.

FORMAT (Repeat for each question):
Q: [Question text]
A) [Option A]
B) [Option B]
C) [Option C]
D) [Option D]
Answer: [Correct Option Letter]
{'Explanation: [1 sentence explanation of correct answer]' if include_explanations else ''}

Output exactly {count} questions based strictly on the content above."""
def build_short_answer_prompt(user_text, difficulty, count):  # Added difficulty
    return f"""Create exactly {count} short answer questions from this content. Follow STRICT rules:

CONTENT:
{user_text.strip()}

DIFFICULTY: {difficulty}
- Easy: 1-2 word answers
- Medium: 1-2 sentence answers
- Hard: 2-3 sentence explanations

FORMAT:
Q: [Question]
A: [Answer]

Generate exactly {count} {difficulty}-level questions."""


# Translate input text if translation is enabled
if enable_translation and target_language:
    with st.spinner(f"Translating content to {target_language}..."):
        try:
            translation_prompt = f"""Translate the following content into {target_language}. Only return the translated version, no explanations.

CONTENT:
{text.strip()}"""

            translation_response = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{"role": "user", "content": translation_prompt}],
                temperature=0.3,
                max_tokens=1500,
            )
            text = translation_response.choices[0].message.content.strip()
        except Exception as e:
            st.error(f"Translation failed: {str(e)}")

# Parsing functions (unchanged)
def parse_mcq_question(question_block):
    lines = [line.strip() for line in question_block.split('\n') if line.strip()]
    
    question_data = {
        'type': 'mcq',
        'question': '',
        'options': [],
        'correct': '',
        'explanation': ''
    }
    
    for line in lines:
        if line.startswith('Q:'):
            question_data['question'] = line[2:].strip()
            break
    
    option_pattern = re.compile(r'^([A-D])\)\s*(.*)')
    for line in lines:
        option_match = option_pattern.match(line)
        if option_match:
            question_data['options'].append(f"{option_match.group(1)}) {option_match.group(2)}")
        
        if line.lower().startswith('answer:'):
            question_data['correct'] = line.split(':')[1].strip().upper()[0]
            
        if line.lower().startswith('explanation:'):
            question_data['explanation'] = line.split(':', 1)[1].strip()
    
    if not (question_data['question'] and len(question_data['options']) == 4 and question_data['correct'] in ['A','B','C','D']):
        return None
    
    return question_data

def parse_short_answer_question(question_block):
    if "Q:" in question_block and "A:" in question_block:
        question, answer = question_block.split("A:", 1)
        return {
            'type': 'short_answer',
            'question': question.replace("Q:", "").strip(),
            'answer': answer.strip()
        }
    return None

# Generate button (updated to pass difficulty)
if st.button(f"✨ Generate {num_questions} {difficulty} {question_type} Questions", use_container_width=True):
    if not text or len(text.strip()) < 30:
        st.warning("Please enter a longer paragraph (at least 30 characters).")
    else:
        with st.spinner(f"Generating {num_questions} {question_type} questions..."):
            try:
                if question_type == "Multiple Choice (MCQ)":
                    prompt = build_mcq_prompt(text, difficulty, num_questions, include_explanations)  # Added difficulty
                    model = "meta-llama/llama-4-scout-17b-16e-instruct"
                    temperature = {"Easy": 0.3, "Medium": 0.5, "Hard": 0.7}[difficulty]  # Added difficulty-based temp
                    max_tokens = 1200
                else:
                    prompt = build_short_answer_prompt(text, difficulty, num_questions)  # Added difficulty
                    model = "meta-llama/llama-4-scout-17b-16e-instruct"
                    temperature = {"Easy": 0.3, "Medium": 0.5, "Hard": 0.7}[difficulty]  # Added difficulty-based temp
                    max_tokens = 800
                
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                
                raw_questions = [q.strip() for q in response.choices[0].message.content.split('\n\n') if q.strip()]
                st.session_state.flashcards = []
                
                for q in raw_questions:
                    if question_type == "Multiple Choice (MCQ)":
                        parsed = parse_mcq_question(q)
                    else:
                        parsed = parse_short_answer_question(q)
                    
                    if parsed:
                        st.session_state.flashcards.append(parsed)
                    else:
                        st.warning(f"Skipped malformed question: {q[:50]}...")
                
                if not st.session_state.flashcards:
                    st.error("No valid questions could be parsed from the response")
                
            except Exception as e:
                st.error(f"Generation Error: {str(e)}")

# Display results (unchanged)
if st.session_state.flashcards:
    if question_type == "Multiple Choice (MCQ)":
        st.markdown(f'<div class="section-header mcq-header">✏️ Multiple Choice Questions ({len(st.session_state.flashcards)} generated)</div>', unsafe_allow_html=True)
        
        for i, mcq in enumerate(st.session_state.flashcards, 1):
            with st.container():
                st.markdown(f"""
                <div class="flashcard mcq-card">
                    <div class="question">❓ {i}. {mcq['question']}</div>
                    <div class="options">
                """, unsafe_allow_html=True)
                
                user_answer = st.radio(
                    f"Select answer for question {i}:",
                    mcq['options'],
                    key=f"mcq_{i}",
                    index=None,
                    label_visibility="collapsed"
                )
                
                if user_answer:
                    selected_option = user_answer[0].upper()
                    is_correct = selected_option == mcq['correct']
                    
                    if is_correct:
                        st.success("✅ Correct!")
                    else:
                        st.error(f"❌ Incorrect. Correct answer is {mcq['correct']})")
                    
                    if mcq['explanation']:
                        st.markdown(f"""
                        <div class="answer sa-answer">💡 Explanation: {mcq['explanation']}</div>
                        """, unsafe_allow_html=True)
                
                st.markdown("</div></div>", unsafe_allow_html=True)
    
    else:
        st.markdown(f'<div class="section-header sa-header">📝 Short Answer Questions ({len(st.session_state.flashcards)} generated)</div>', unsafe_allow_html=True)
        
        for i, sa in enumerate(st.session_state.flashcards, 1):
            with st.expander(f"Question {i}: {sa['question']}", expanded=False):
                st.markdown(f"""
                <div class="flashcard sa-card">
                    <div class="answer sa-answer">💡 {sa['answer']}</div>
                </div>
                """, unsafe_allow_html=True)

# Raw Output (cleaned & enhanced)
st.markdown("---")
with st.expander("📋 Review Output"):
    raw_blocks = []
    for q in st.session_state.flashcards:
        if q['type'] == 'mcq':
            options_block = "\n".join(q['options'])
            explanation_block = f"\nExplanation: {q.get('explanation','')}" if q.get('explanation') else ""
            block = f"Q: {q['question']}\n{options_block}\nAnswer: {q['correct']}{explanation_block}"
        else:
            block = f"Q: {q['question']}\nA: {q['answer']}"
        raw_blocks.append(block)
    
    st.code("\n\n".join(raw_blocks))

# ⬇️ Safe download function with UTF-8 encoding
def download_button(data, filename, file_label):
    if isinstance(data, str):
        data = data.encode('utf-8')  # ensure encoding for all files
    b64 = base64.b64encode(data).decode()
    href = f'<a href="data:file/txt;base64,{b64}" download="{filename}">{file_label}</a>'
    return href

# ⬇️ Create formatted export data (with UTF-8 protection)
def generate_export_data():
    flashcards = st.session_state.flashcards
    csv_rows = []
    anki_rows = []

    for q in flashcards:
        if q['type'] == 'mcq':
            csv_rows.append({
                'Question': q['question'],
                'Option A': q['options'][0][3:],
                'Option B': q['options'][1][3:],
                'Option C': q['options'][2][3:],
                'Option D': q['options'][3][3:],
                'Answer': q['correct'],
                'Explanation': q.get('explanation', '')
            })
            answer_text = q['options'][ord(q['correct']) - 65][3:]
            back = f"{answer_text}" + (f"<br><i>{q['explanation']}</i>" if q.get('explanation') else "")
            anki_rows.append({'Front': q['question'], 'Back': back})
        else:
            csv_rows.append({
                'Question': q['question'],
                'Answer': q['answer']
            })
            anki_rows.append({'Front': q['question'], 'Back': q['answer']})

    # Encode all text properly to prevent mojibake
    csv_data = pd.DataFrame(csv_rows).to_csv(index=False, encoding='utf-8')
    json_data = json.dumps(flashcards, ensure_ascii=False, indent=2)
    anki_data = pd.DataFrame(anki_rows).to_csv(index=False, header=False, encoding='utf-8')

    return csv_data, json_data, anki_data

# ⬇️ Show export section
if st.session_state.flashcards:
    with st.expander("📤 Export Flashcards", expanded=False):
        csv_data, json_data, anki_data = generate_export_data()

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(download_button(csv_data, "flashcards.csv", "⬇️ Download CSV"), unsafe_allow_html=True)
            st.markdown(download_button(json_data, "flashcards.json", "⬇️ Download JSON"), unsafe_allow_html=True)
        with col2:
            st.markdown(download_button(anki_data, "flashcards_anki.csv", "⬇️ Download Anki CSV"), unsafe_allow_html=True)
            st.markdown(download_button(csv_data, "flashcards_quizlet.csv", "⬇️ Download Quizlet CSV"), unsafe_allow_html=True)
