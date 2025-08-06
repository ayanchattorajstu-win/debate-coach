import streamlit as st
import openai
import json
import re
from pydantic import BaseModel
from typing import List, Optional

# --- Data Models ---
class Evidence(BaseModel):
    evidence_description: str
    source_or_instance: str

class Argument(BaseModel):
    argument_title: Optional[str]
    argument: Optional[str]
    argument_description: Optional[str]
    supporting_evidence: Optional[List[Evidence]]
    evidence_hint: Optional[str]
    famous_quote: Optional[str] = ""

class DebateArguments(BaseModel):
    arguments: List[Argument]

class SimpleArgList(BaseModel):
    arguments: List[Argument]

class Rebuttal(BaseModel):
    original_argument_title: str
    counter_argument: str
    counter_evidence: Evidence

class Rebuttals(BaseModel):
    rebuttals: List[Rebuttal]

# --- Constants ---
PROMPT_STYLES = {
    "wsdc": "You are an elite debate strategist trained for World Schools Debating Championships. Generate deeply analytical, high-impact arguments with strong causal reasoning. Use real statistics or historical examples. Return 3 serious arguments + 2 evidence points each in JSON only.",
    "aggressive": "You are an aggressive strategist preparing for a knockout debate. Arguments must be bold, piercing, and high-impact, backed by ruthless evidence. Return 3 sharp arguments + 2 striking evidence points in JSON only.",
    "policy": "You are a top policy debater trained at university level. Provide highly analytical, cause-effect driven arguments with empirical data. Return 3 sophisticated arguments + 2 precise evidence points in JSON only.",
    "rhetorical": "You are a championship public speaker. Craft persuasive, emotionally compelling yet logically sound arguments using vivid examples. Return 3 persuasive arguments + 2 vivid evidence points in JSON only."
}

# --- Utility Functions ---
def extract_json(raw_text):
    try:
        match = re.search(r"\{(?:[^{}]|(?R))*\}", raw_text, flags=re.DOTALL)
        if match:
            return match.group(0)
    except Exception:
        pass
    try:
        match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
        if match:
            return match.group(0)
    except Exception:
        pass
    return None

# --- Generation and Scoring Functions ---

@st.cache_data(show_spinner=False)
def generate_arguments(topic, stance, style="wsdc"):
    persona = "Speak in an optimistic, forward-thinking tone emphasizing opportunity, progress, and upside." if stance.lower() == "in favour" else "Speak in a skeptical, hard-hitting tone focusing on risks, downsides, and critique."
    system_prompt = f"""{persona}
{PROMPT_STYLES.get(style, PROMPT_STYLES["wsdc"])}

IMPORTANT: Output ONLY JSON EXACTLY like this, no extra text:
{{
  "arguments": [
     {{
       "argument_title": "...",
       "argument_description": "...",
       "supporting_evidence": [
          {{"evidence_description": "...", "source_or_instance": "..."}}
       ],
       "famous_quote":"A relevant famous quotation (include author name)."
     }}
  ]
}}
"""
    user_prompt = f'Topic: "{topic}"\nStance: {stance}'
    resp = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}],
        max_tokens=1500,
        temperature=0.7
    )
    raw = resp.choices[0].message.content.strip()
    try:
        return DebateArguments.model_validate_json(raw)
    except Exception:
        json_str = extract_json(raw)
        if json_str:
            return DebateArguments.model_validate_json(json_str)
        else:
            st.error("Failed to parse arguments JSON.")
            st.text(raw)
            return None

@st.cache_data(show_spinner=False)
def generate_opponents(topic, style="wsdc"):
    system_prompt = """
You must ONLY output a JSON object exactly like this, nothing else:
{
  "arguments": [
    {
      "argument": "...",
      "evidence_hint": "...",
      "famous_quote": "..."
    },
    ...
  ]
}
Do not add explanations or wrap output in any text.
"""
    user_prompt = (
        f'Motion: "{topic}". Provide THREE distinct arguments AGAINST the motion, '
        'return JSON object with key "arguments" as an array of 3 arguments.'
    )
    resp = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}],
        max_tokens=800,
        temperature=0.7
    )
    raw_output = resp.choices[0].message.content.strip()
    json_str = extract_json(raw_output)
    if not json_str:
        st.error("Could not find JSON in model output for opponents.")
        st.text(raw_output)
        return None
    try:
        return SimpleArgList.model_validate_json(json_str)
    except Exception as e:
        st.error(f"Error validating opponents JSON: {e}")
        st.text(json_str)
        return None

@st.cache_data(show_spinner=False)
def generate_rebuttals(opponent_json):
    rebut_sys = """
You are a rapid rebuttal strategist. For EACH incoming argument (one at a time),
produce exactly one counter-argument and one counter-evidence.
Output JSON with EXACT keys:
{
  "original_argument_title":"...",
  "counter_argument":"...",
  "counter_evidence":{
     "evidence_description":"...",
     "source_or_instance":"..."
  }
}
No extra keys. No array wrapper.
"""
    rebutted = []
    try:
        parsed_opp = SimpleArgList.model_validate_json(opponent_json)
    except Exception as e:
        st.error(f"Opponent JSON invalid: {e}\n{opponent_json}")
        return []

    for arg in parsed_opp.arguments:
        mini = {"arguments": [arg.model_dump()]}
        user_prompt = "Opponent argument:\n" + json.dumps(mini)
        resp = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"system","content":rebut_sys},{"role":"user","content":user_prompt}],
            max_tokens=500,
            temperature=0.7
        )
        raw = resp.choices[0].message.content.strip()
        try:
            parsed = Rebuttals.model_validate_json(f'{{"rebuttals":[{raw}]}}')
            rebutted.append(parsed.rebuttals[0])
        except Exception as e:
            st.warning(f"Could not parse rebuttal for arg '{arg.argument}': {e}\nRaw: {raw}")

    return rebutted

@st.cache_data(show_spinner=False)
def score_rebuttal(rebuttal_text, opponent_arg_title, topic, style):
    score_prompt = f"""
You are a debate coach. Score this HUMAN REBUTTAL (1–10 each):
Logic, Evidence, Relevance, Style/Clarity.
Opponent argument title: "{opponent_arg_title}"
Motion: "{topic}"
Human rebuttal: "{rebuttal_text}"
Output STRICT JSON like:
{{"Logic":7,"Evidence":5,"Relevance":9,"Style":6,"Suggestion":"..."}}
"""
    r = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"system","content":"You are scoring rebuttals."},{"role":"user","content":score_prompt}],
        max_tokens=200, temperature=0.3
    )
    try:
        return json.loads(r.choices[0].message.content.strip())
    except Exception as e:
        st.error(f"Error parsing scoring JSON: {e}")
        st.text(r.choices[0].message.content)
        return None

# --- Display Functions ---
def display_argument_cards(debate_args: DebateArguments):
    for idx, arg in enumerate(debate_args.arguments, start=1):
        st.subheader(f"ARGUMENT {idx}: {arg.argument_title or arg.argument}")
        desc = arg.argument_description or arg.argument or ""
        st.write(desc)
        if arg.supporting_evidence:
            for ev in arg.supporting_evidence:
                st.write(f"✅ {ev.evidence_description} ({ev.source_or_instance})")
        if arg.evidence_hint:
            st.write(f"💡 Evidence hint: {arg.evidence_hint}")
        if arg.famous_quote:
            st.write(f"💬 *{arg.famous_quote}*")
        st.markdown("---")

def display_rebuttal_cards(rebut_obj: Rebuttals):
    for r in rebut_obj.rebuttals:
        st.subheader(f"REBUTTAL to \"{r.original_argument_title}\"")
        st.write(f"→ {r.counter_argument}")
        ev = r.counter_evidence
        st.write(f"✅ {ev.evidence_description} ({ev.source_or_instance})")
        st.markdown("---")

# --- Streamlit UI ---

st.title("AI Debate Trainer")

# Read OpenAI API key from secrets.toml
if "openai_api_key" not in st.secrets:
    st.error("OpenAI API key not found in Streamlit secrets. Please add it as openai_api_key.")
    st.stop()
openai.api_key = st.secrets["openai_api_key"]

# Debate setup
topic = st.text_input("Debate Topic", value="This House Would ban political advertising on social media")
stance = st.radio("Your Stance", options=["in favour", "against"])
style = st.selectbox("Debate Style", options=list(PROMPT_STYLES.keys()))

if 'your_arguments' not in st.session_state:
    st.session_state.your_arguments = None
if 'opponent_arguments' not in st.session_state:
    st.session_state.opponent_arguments = None
if 'opponent_rebuttals' not in st.session_state:
    st.session_state.opponent_rebuttals = None

if st.button("Generate My Arguments"):
    with st.spinner("Generating arguments..."):
        args = generate_arguments(topic, stance, style)
        st.session_state.your_arguments = args

if st.session_state.your_arguments:
    st.header("Your Arguments")
    display_argument_cards(st.session_state.your_arguments)

if st.button("Simulate Opponent Arguments"):
    with st.spinner("Simulating opponent arguments..."):
        opp_args = generate_opponents(topic, style)
        if opp_args:
            st.session_state.opponent_arguments = opp_args
            st.session_state.opponent_rebuttals = None  # reset rebuttals

if st.session_state.opponent_arguments:
    st.header("Simulated Opponent Arguments")
    for idx, arg in enumerate(st.session_state.opponent_arguments.arguments):
        st.markdown(f"**Opponent Argument {idx+1}:** {arg.argument}")
        if arg.evidence_hint:
            st.write(f"💡 Evidence hint: {arg.evidence_hint}")
        if arg.famous_quote:
            st.write(f"💬 *{arg.famous_quote}*")

        st.subheader(f"Your Rebuttal to Argument {idx+1}")
        key = f"rebuttal_{idx}"
        rebuttal_text = st.text_area("Type your rebuttal here:", key=key)

        col1, col2 = st.columns(2)

        with col1:
            if st.button(f"Score My Rebuttal {idx+1}", key=f"score_{idx}"):
                if not rebuttal_text:
                    st.warning("Please enter your rebuttal to score.")
                else:
                    score = score_rebuttal(rebuttal_text, arg.argument, topic, style)
                    if score:
                        st.write("### Rebuttal Scores:")
                        for k, v in score.items():
                            if k != "Suggestion":
                                st.write(f"**{k}:** {v}")
                        st.write(f"**Suggestion:** {score.get('Suggestion', '')}")

        with col2:
            if st.button(f"Reveal AI Rebuttal {idx+1}", key=f"ai_rebuttal_{idx}"):
                with st.spinner("Generating AI rebuttal..."):
                    single_arg_json = json.dumps({"arguments": [arg.model_dump()]})
                    ai_rebuttals = generate_rebuttals(single_arg_json)
                    if ai_rebuttals:
                        display_rebuttal_cards(Rebuttals(rebuttals=ai_rebuttals))

        st.markdown("---")

st.sidebar.header("How to Use")
st.sidebar.markdown("""
1. Add your OpenAI API key in Streamlit secrets as `openai_api_key`.
2. Enter the debate topic.
3. Select your stance and debate style.
4. Click **Generate My Arguments** to get your arguments.
5. Click **Simulate Opponent Arguments** to get opponent points.
6. Practice rebuttals by typing in the text areas.
7. Score your rebuttal and see AI's suggested rebuttal.
""")
