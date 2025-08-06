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

def generate_one_arg(topic, style, stance="in favour", retries=3):
    user = f'Motion: "{topic}". Give one strong argument {stance}, with one evidence hint and a short famous quote.'
    for i in range(1, retries+1):
        r = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"system","content":SYSTEM_SIMPLE},
                      {"role":"user","content":user}],
            max_tokens=350,temperature=0.7
        )
        raw = r.choices[0].message.content.strip()
        try:
            return SimpleArg.model_validate_json(raw)
        except Exception:
            st.warning(f"Attempt {i}/{retries} failed to parse: {raw}")
    st.error("Failed all attempts. Final raw:")
    st.text(raw)
    return None

def generate_opponents(topic, style):
    prompt = {"role":"system","content":SYSTEM_SIMPLE + "You are now opposing the motion."}
    user=f'Motion: "{topic}". Provide THREE arguments AGAINST in an array as JSON: {{"arguments":[{{...}},...]}}'
    r=openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[prompt,{"role":"user","content":user}],
        max_tokens=800
    )
    return SimpleArgList.model_validate_json(r.choices[0].message.content.strip())

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

if st.button("🎲 Random Motion"):
    st.session_state['topic']=random.choice(DEFAULT_MOTIONS)

topic = st.text_input("Debate Motion:", st.session_state.get("topic",""))
style = st.selectbox("Style", ["wsdc","aggressive","policy","rhetorical"])

if st.button("Generate Arguments (in favour)"):
    st.header("Your Arguments:")
    simple_args=[]
    for i in range(1,4):
        x=generate_one_arg(topic,style,"in favour")
        if x: 
            st.subheader(f"ARGUMENT {i}:")
            st.write(x.argument)
            st.write(f"📌 Evidence hint: {x.evidence_hint}")
            st.write(f"💬 {x.famous_quote}")
        simple_args.append(x)

    st.divider()
    st.header("Simulated Opponent:")
    opp=generate_opponents(topic,style)

    for idx,arg in enumerate(opp.arguments):
        st.subheader(f"Opposition {idx+1}:")
        st.write(arg.argument)
        st.write(f"📌 {arg.evidence_hint}")
        st.write(f"💬 {arg.famous_quote}")

        reb=st.text_area("Your rebuttal:", key=f"rr_{idx}")
        if st.button("Score rebuttal", key=f"s_{idx}"):
            st.json(score_rebuttal(reb,arg.argument,topic))
        if st.button("Reveal AI rebuttal", key=f"a_{idx}"):
            st.json(ai_rebuttal(arg))
