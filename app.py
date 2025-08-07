import streamlit as st
import openai
import json
from pydantic import BaseModel
from typing import List
import random

# === Secure key from Streamlit Cloud secrets ===
openai.api_key = st.secrets["openai_api_key"]

# === Minimal models ===
class SimpleArg(BaseModel):
    argument: str
    evidence_hint: str
    famous_quote: str

class SimpleArgList(BaseModel):
    arguments: List[SimpleArg]

# === 20 motions ===
DEFAULT_MOTIONS = [
    "This House Would ban TikTok",
    "This House Believes that AI will replace teachers",
    "This House Would remove zoos",
    "This House Believes money spent on space exploration is a waste",
    "This House Would ban private cars in cities",
    "This House Believes exams do more harm than good",
    "This House Would make voting compulsory",
    "This House Believes that influencers are bad role models",
    "This House Would legalise all drugs",
    "This House Believes that patriotism is dangerous",
    "This House Would tax the rich heavily to fund basic income",
    "This House Believes that animals have equal rights",
    "This House Would abolish homework",
    "This House Believes social media does more harm than good",
    "This House Would ban animal testing",
    "This House Believes nuclear energy is the future",
    "This House Would replace politicians with experts",
    "This House Believes tradition holds back progress",
    "This House Would limit AI research",
    "This House Believes success is luck, not hard work"
]

# === generation prompt ===
SYSTEM_SIMPLE = """
You must ONLY output a JSON object with the following keys exactly:
{
 "argument":"...",
 "evidence_hint":"...",
 "famous_quote":"..."
}
Do not use extra keys, do not wrap in array, do not add explanations.
"""

def generate_one_arg(user_prompt, retries=3):
    # This function now takes the full user prompt as an argument
    for i in range(1, retries+1):
        try:
            r = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role":"system","content":SYSTEM_SIMPLE},
                          {"role":"user","content":user_prompt}],
                max_tokens=350,temperature=0.7
            )
            raw = r.choices[0].message.content.strip()
            return SimpleArg.model_validate_json(raw)
        except Exception as e:
            st.warning(f"Attempt {i}/{retries} failed to parse JSON from AI: {e}")
            st.text(f"Raw AI Output: {raw}")
    st.error(f"Failed all attempts. Final raw: {raw}")
    return None

def generate_opponents(topic, style, retries=3):
    """
    Generates three truly opposing arguments designed to dismantle the motion.
    """
    sys_prompt = f"""
You are a ruthless debate opponent whose only goal is to DISPROVE the motion: "{topic}".
You must present hard-hitting, critical arguments that attack the *foundational assumptions* behind the motion.

DO NOT present reasons why the motion might partially work.
DO NOT hedge or show balance.
You must argue that the motion is fundamentally WRONG, harmful, misguided, or illogical.

OUTPUT FORMAT ONLY:
[
  {{
    "argument": "<one-sentence direct rebuttal>",
    "evidence_hint": "<very specific example, trend, or reference>",
    "famous_quote": "<short sharp quote>"
  }},
  ...
]

EXAMPLES of OPPOSITION:
- Motion: "THBT social media is beneficial" -> Opp argument: "Social media destroys mental health by promoting addictive and anxiety-inducing behaviours."
- Motion: "TH would ban zoos" -> Opp argument: "Zoos preserve endangered species far more effectively than leaving them in the wild."

Now produce 3 such opposing arguments in the JSON format above.
"""
    user = f'Motion: "{topic}". Provide EXACTLY THREE opposing arguments, aiming to *destroy* this motion.'

    for i in range(1, retries + 1):
        try:
            r = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role":"system", "content": sys_prompt},
                          {"role":"user", "content": user}],
                max_tokens=650,
                temperature=0.6
            )
            raw = r.choices[0].message.content.strip()
            parsed_list = json.loads(raw)
            arguments = [SimpleArg.model_validate(item) for item in parsed_list]
            return SimpleArgList(arguments=arguments)

        except Exception as e:
            st.warning(f"Attempt {i}/{retries} failed to parse JSON from AI: {e}")
            st.text(f"Raw AI Output: {raw}")

    st.error("Failed to generate and parse opponent arguments after multiple attempts.")
    return SimpleArgList(arguments=[])

def score_rebuttal(text, opp_argument, topic):
    sc=f"""Score this rebuttal (1–10 Logic,Evidence,Relevance,Style):
Opponent arg: "{opp_argument}" Motion: "{topic}" Rebuttal: "{text}"
Return JSON: {{"Logic":7,"Evidence":6,"Relevance":8,"Style":5,"Suggestion":"..."}}"""
    r=openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"system","content":"debate coach"},{"role":"user","content":sc}],
        max_tokens=200,temperature=0.3
    )
    return json.loads(r.choices[0].message.content.strip())

def ai_rebuttal(arg_obj):
    sys="""Only output JSON: {"original_argument":"...","answer":"..."}"""
    u=f'Opponent: {arg_obj.argument}'
    r=openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"system","content":sys},{"role":"user","content":u}],
        max_tokens=300
    )
    return json.loads(r.choices[0].message.content.strip())

# ==================== Streamlit UI =======================

st.title("AI Debate Trainer (Simplified Version)")

if "topic" not in st.session_state:
    st.session_state['topic'] = ""
if "opponent_args" not in st.session_state:
    st.session_state['opponent_args'] = []
if "my_args" not in st.session_state:
    st.session_state['my_args'] = []

if st.button("🎲 Random Motion"):
    st.session_state['topic']=random.choice(DEFAULT_MOTIONS)
    st.session_state['opponent_args'] = []
    st.session_state['my_args'] = []

topic = st.text_input("Debate Motion:", st.session_state.get("topic",""))
style = st.selectbox("Style", ["wsdc","aggressive","policy","rhetorical"])

if st.button("Generate Arguments (in favour)"):
    with st.spinner("Generating arguments..."):
        st.session_state['my_args']=[]
        
        # Argument 1: Moral/Ethical
        p1 = f'Motion: "{topic}". Give one strong argument in favour, focused on moral or ethical implications. The evidence hint should be specific, e.g., a philosophical principle, a historical precedent, or a legal framework.'
        x1 = generate_one_arg(p1)
        if x1:
            st.session_state['my_args'].append(x1)

        # Argument 2: Economic/Practical
        p2 = f'Motion: "{topic}". Give one strong argument in favour, focused on economic or practical benefits. The evidence hint should be specific, e.g., a specific economic model, a case study, or a policy impact report.'
        x2 = generate_one_arg(p2)
        if x2:
            st.session_state['my_args'].append(x2)

        # Argument 3: Societal/Developmental
        p3 = f'Motion: "{topic}". Give one strong argument in favour, focused on broader societal or human developmental benefits. The evidence hint should be specific, e.g., a sociological trend, a psychological study, or a UN report.'
        x3 = generate_one_arg(p3)
        if x3:
            st.session_state['my_args'].append(x3)

        opponent_args_list = generate_opponents(topic, style)
        if opponent_args_list:
            st.session_state['opponent_args'] = opponent_args_list.arguments

if st.session_state['my_args']:
    st.header("Your Arguments:")
    for i, arg_obj in enumerate(st.session_state['my_args']):
        st.subheader(f"ARGUMENT {i+1}:")
        st.write(arg_obj.argument)
        st.write(f"📌 Evidence hint: {arg_obj.evidence_hint}")
        st.write(f"💬 {arg_obj.famous_quote}")

if st.session_state['opponent_args']:
    st.divider()
    st.header("Simulated Opponent:")
    for idx, arg in enumerate(st.session_state['opponent_args']):
        st.subheader(f"Opposition {idx+1}:")
        st.write(arg.argument)
        st.write(f"📌 {arg.evidence_hint}")
        st.write(f"💬 {arg.famous_quote}")

        reb=st.text_area("Your rebuttal:", key=f"rr_{idx}")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Score rebuttal", key=f"s_{idx}"):
                with st.spinner("Scoring..."):
                    st.json(score_rebuttal(reb,arg.argument,topic))
        with col2:
            if st.button("Reveal AI rebuttal", key=f"a_{idx}"):
                with st.spinner("Generating AI rebuttal..."):
                    st.json(ai_rebuttal(arg))
