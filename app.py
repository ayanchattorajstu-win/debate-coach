import streamlit as st
import openai
import json
from pydantic import BaseModel
from typing import List
import random

# ======== 0. Secure API key (set in Streamlit Cloud Secrets) =========
openai.api_key = st.secrets["openai_api_key"]

# ======== 1. Data Models ============================================
class Evidence(BaseModel):
    evidence_description: str
    source_or_instance: str

class Argument(BaseModel):
    argument_title: str
    argument_description: str
    supporting_evidence: List[Evidence]
    famous_quote: str

class DebateArguments(BaseModel):
    arguments: List[Argument]

class Rebuttal(BaseModel):
    original_argument_title: str
    counter_argument: str
    counter_evidence: Evidence

class Rebuttals(BaseModel):
    rebuttals: List[Rebuttal]

# ======== 2. Motion Bank (20 General) ================================
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

# ======== 3. Style Presets ===========================================
PROMPT_STYLES = {
    "wsdc": """You are an elite WSDC strategist. Return one JSON argument with structure:
{"argument_title":"...","argument_description":"...","supporting_evidence":[{"evidence_description":"...","source_or_instance":"..."}],"famous_quote":"..."}""",
    "aggressive": """You are an aggressive strategist. Return one JSON argument in the same structure as above.""",
    "policy": """You are a policy debater. Return one JSON argument in the same structure.""",
    "rhetorical": """You are a public speaker. Return one JSON argument in the same structure."""
}

# ======== 4. Helper Display =========================================
def show_argument(a:Argument, i:int):
    st.subheader(f"ARGUMENT {i}: {a.argument_title}")
    st.write(a.argument_description)
    for ev in a.supporting_evidence:
        st.write(f"✅ {ev.evidence_description} ({ev.source_or_instance})")
    if a.famous_quote:
        st.write(f"💬 _{a.famous_quote}_")
    st.markdown("---")

def show_rebuttal(r:Rebuttal):
    st.subheader(f"REBUTTAL to \"{r.original_argument_title}\"")
    st.write(f"→ {r.counter_argument}")
    ev = r.counter_evidence
    st.write(f"✅ {ev.evidence_description} ({ev.source_or_instance})")
    st.markdown("---")
def generate_one_argument(topic, style):
    """
    Generates exactly one supporting argument for the motion.
    Returns an Argument object if valid JSON is produced, or None (with raw text shown to user).
    """
    system_prompt = (
        PROMPT_STYLES[style] +
        """
IMPORTANT: You MUST output a single JSON OBJECT with these EXACT keys, no more/no less:
{
  "argument_title": "...",
  "argument_description": "...",
  "supporting_evidence":[
      {"evidence_description":"...","source_or_instance":"..."}
  ],
  "famous_quote":"..."
}
Do NOT output markdown, no backticks, no lists, no explanation. Only raw JSON object.
"""
    )

    user_prompt = f"Motion: \"{topic}\". Generate ONE argument firmly in favour."

    res = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"system","content":system_prompt},
                  {"role":"user","content":user_prompt}],
        max_tokens=650,
        temperature=0.7
    )
    raw = res.choices[0].message.content.strip()

    try:
        return Argument.model_validate_json(raw)
    except Exception as e:
        st.error("Could not parse JSON. Raw model output shown below to help adjust prompting.")
        st.text(raw)
        return None
# ======== 5. OpenAI Functions =======================================
def generate_one_argument(topic, style):
    """Generate exactly one argument JSON."""
    system_prompt = PROMPT_STYLES[style]
    user_prompt = f"Motion: \"{topic}\". Generate one argument IN FAVOUR."
    res = openai.chat.completions.create(
        model="gpt-3.5-turbo",messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}],
        max_tokens=550,temperature=0.7
    )
    return Argument.model_validate_json(res.choices[0].message.content.strip())

def simulate_opponent(topic, style):
    """Generate 3 opposition arguments."""
    system_prompt = PROMPT_STYLES[style]+"""
Now argue AGAINST the motion. Return ONLY JSON:
{"arguments":[{...}]}"""
    user = f"Motion: \"{topic}\". Provide 3 arguments AGAINST."
    res=openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"system","content":system_prompt},{"role":"user","content":user}],
        max_tokens=1100,temperature=0.7
    )
    return DebateArguments.model_validate_json(res.choices[0].message.content.strip())

def score_rebuttal(text, opp_title, topic, style):
    prompt=f"""You are a debate coach. Score this (1–10 Logic, Evidence, Relevance, Style).
Opponent arg: "{opp_title}" | Motion: "{topic}" | Rebuttal: "{text}"
Return JSON like {{"Logic":7,"Evidence":6,"Relevance":8,"Style":5,"Suggestion":"..."}}"""
    r=openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"system","content":"You are a coach."},{"role":"user","content":prompt}],
        max_tokens=200,temperature=0.3
    )
    return json.loads(r.choices[0].message.content.strip())

def generate_rebuttal_for_arg(argument:Argument):
    sys="""Return ONLY JSON: {"original_argument_title":"...","counter_argument":"...","counter_evidence":{"evidence_description":"...","source_or_instance":"..."}}"""
    mini={"arguments":[argument.model_dump()]}
    r=openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"system","content":sys},{"role":"user","content":json.dumps(mini)}],
        max_tokens=500,temperature=0.7
    )
    raw=r.choices[0].message.content.strip()
    return Rebuttals.model_validate_json('{"rebuttals":['+raw+']}').rebuttals[0]

# ======== 6. Streamlit UI ===========================================
st.title("AI Debate Trainer")

# Randomiser
if st.button("🎲 Random Motion"):
    st.session_state['topic']= random.choice(DEFAULT_MOTIONS)

topic=st.text_input("Debate Motion:", st.session_state.get("topic",""))
style=st.selectbox("Debater Style", list(PROMPT_STYLES.keys()))

if st.button("Generate Constructive (in favour)"):
    # generate 3 arguments one-by-one
    args_list=[]
    for i in range(1,4):
        a=generate_one_argument(topic,style)
        show_argument(a,i)
        args_list.append(a)

    st.divider()
    st.header("Simulated Opposition")
    opp = simulate_opponent(topic,style)

    for idx, oa in enumerate(opp.arguments):
        st.subheader(f"Opposition Arg {idx+1}: {oa.argument_title}")
        st.write(oa.argument_description)
        for ev in oa.supporting_evidence:
            st.write(f"- {ev.evidence_description} ({ev.source_or_instance})")
        st.write(f"💬 {oa.famous_quote}")

        user_reb=st.text_area("Your rebuttal:", key=f"r_{idx}")
        if st.button("Score My Rebuttal",key=f"s_{idx}"):
            st.json(score_rebuttal(user_reb, oa.argument_title, topic, style))
        if st.button("Reveal AI Rebuttal",key=f"a_{idx}"):
            rb=generate_rebuttal_for_arg(oa)
            show_rebuttal(rb)
