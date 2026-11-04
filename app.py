import streamlit as st
import json
import math
import os
from openai import OpenAI
from typing import Dict, Any, List

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Dynamic AI Code Rectifier & Testing Engine",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Dynamic AI Code Rectifier & Testing Engine")
st.caption("Auto-discovering bugs, edge cases, and running regression tests.")
st.divider()

# ==========================================
# SECURE API KEY RETRIEVAL & MODEL DISCOVERY
# ==========================================
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")

if not GROQ_API_KEY:
    st.error("⚠️ Groq API Key not detected! Please ensure `GROQ_API_KEY` is in `.streamlit/secrets.toml`.")
    st.stop()

# Initialize Groq client
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# Fetch models from your active account and filter out Audio, TTS, and Guard models
try:
    all_models = [m.id for m in client.models.list().data]
    
    # Exclude audio/TTS/safety models that require special agreements or fail on text
    valid_chat_models = [
        m for m in all_models 
        if not any(bad in m.lower() for bad in ["whisper", "guard", "orpheus", "canopy", "tts", "audio", "vision"])
    ]
    
    if not valid_chat_models:
        valid_chat_models = ["openai/gpt-oss-20b", "llama-3.3-70b-versatile"]
except Exception as e:
    st.error(f"Failed to connect to Groq: {str(e)}")
    st.stop()

# Display active model selector so you always use a valid model
col_m1, col_m2 = st.columns([3, 1])
with col_m1:
    selected_model = st.selectbox(
        "Active Groq Model (Auto-detected from your account):",
        options=valid_chat_models,
        index=0
    )
with col_m2:
    st.write("")
    st.write("")
    st.caption("🟢 Connected to Groq")

# ==========================================
# CORE AI ANALYSIS ENGINE
# ==========================================
def analyze_with_groq(code_str: str, model_name: str) -> Dict[str, Any]:
    system_prompt = """
    You are an expert QA Engineer and Python Auditor.
    Analyze the user's arbitrary Python code and return a STRICT JSON object with:
    {
      "function_name": "exact_name_of_the_primary_function",
      "bugs": [
        {"type": "Error Title", "location": "code line", "explanation": "why this fails"}
      ],
      "edge_cases": [
        "Description of boundary condition or edge case 1",
        "Description of boundary condition or edge case 2"
      ],
      "rectified_code": "Full corrected python code string with matching function name.",
      "test_cases": [
        {
          "id": "TC01",
          "name": "Test description",
          "args": [arg1, arg2],
          "expected": expected_return_value
        }
      ]
    }
    Rules:
    - 'args' MUST be a list containing positional arguments to pass with *args.
    - Provide at least 5 varied test cases (normal, edge cases, boundary values).
    - Return RAW JSON only, without markdown fences.
    """

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Analyze and rectify this code:\n\n{code_str}"}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

# ==========================================
# DYNAMIC TEST RUNNER
# ==========================================
def execute_dynamic_suite(code_str: str, func_name: str, test_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scope = {}
    results = []

    try:
        exec(code_str, scope)
    except Exception as e:
        for tc in test_cases:
            results.append({
                "id": tc["id"],
                "name": tc["name"],
                "args": str(tc.get("args")),
                "expected": str(tc.get("expected")),
                "actual": "Compilation Error",
                "status": "FAIL",
                "error": str(e)
            })
        return results

    func = scope.get(func_name)
    if not func or not callable(func):
        for tc in test_cases:
            results.append({
                "id": tc["id"],
                "name": tc["name"],
                "args": str(tc.get("args")),
                "expected": str(tc.get("expected")),
                "actual": "Function Not Found",
                "status": "FAIL",
                "error": f"Function '{func_name}' not defined"
            })
        return results

    for tc in test_cases:
        args = tc.get("args", [])
        expected = tc.get("expected")
        try:
            actual = func(*args)
            if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
                passed = math.isclose(actual, expected, rel_tol=1e-5, abs_tol=1e-5)
            else:
                passed = (actual == expected)

            results.append({
                "id": tc["id"],
                "name": tc["name"],
                "args": str(args),
                "expected": str(expected),
                "actual": str(actual),
                "status": "PASS" if passed else "FAIL",
                "error": None
            })
        except Exception as e:
            results.append({
                "id": tc["id"],
                "name": tc["name"],
                "args": str(args),
                "expected": str(expected),
                "actual": f"Raised {type(e).__name__}",
                "status": "FAIL",
                "error": str(e)
            })
            
    return results

# ==========================================
# USER INTERFACE
# ==========================================
st.subheader("1. Code Input")

default_code = '''def calculate_factorial(n):
    result = 0
    for i in range(0, n):
        result = result * i
    return result

print(calculate_factorial(5))
'''

user_code = st.text_area(
    "Python Code Editor:",
    value=default_code,
    height=180
)

if st.button("🚀 Analyze, Rectify & Execute Dynamic Tests", type="primary"):
    with st.spinner(f"Analyzing code using {selected_model}..."):
        try:
            analysis = analyze_with_groq(user_code, selected_model)
        except Exception as e:
            st.error(f"Error during AI analysis: {str(e)}")
            st.stop()

    func_name = analysis.get("function_name", "target_function")
    rectified_code = analysis.get("rectified_code", "")
    test_cases = analysis.get("test_cases", [])

    st.success(f"🎯 Target function identified: `{func_name}`")

    # Section 2 & 3: Bugs vs Rectified Code
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("2. Bug & Edge Case Analysis")
        st.markdown("**Identified Bugs:**")
        for i, bug in enumerate(analysis.get("bugs", []), 1):
            with st.expander(f"❌ Bug {i}: {bug.get('type')}", expanded=True):
                st.markdown(f"**Location:** `{bug.get('location')}`")
                st.write(bug.get("explanation"))

        st.markdown("**Edge Cases Discovered:**")
        for ec in analysis.get("edge_cases", []):
            st.markdown(f"- ⚠️ {ec}")

    with col2:
        st.subheader("3. Rectified Python Code")
        st.code(rectified_code, language="python")

    # Section 4: Display Test Cases
    st.subheader("4. Generated Dynamic Test Suite")
    st.table([
        {"ID": tc["id"], "Scenario": tc["name"], "Inputs (Args)": str(tc["args"]), "Expected Return": str(tc["expected"])}
        for tc in test_cases
    ])

    # Section 5: Side-by-Side Dynamic Execution
    st.subheader("5. Dynamic Test Execution Comparison")
    col_orig, col_fixed = st.columns(2)

    with col_orig:
        st.markdown("#### Faulty Code (Before Fix)")
        orig_results = execute_dynamic_suite(user_code, func_name, test_cases)
        st.dataframe(
            [{"Test ID": r["id"], "Scenario": r["name"], "Actual Output": r["actual"], "Status": "✅ PASS" if r["status"] == "PASS" else "❌ FAIL"} for r in orig_results],
            use_container_width=True
        )

    with col_fixed:
        st.markdown("#### Rectified Code (After Fix)")
        fixed_results = execute_dynamic_suite(rectified_code, func_name, test_cases)
        st.dataframe(
            [{"Test ID": r["id"], "Scenario": r["name"], "Actual Output": r["actual"], "Status": "✅ PASS" if r["status"] == "PASS" else "❌ FAIL"} for r in fixed_results],
            use_container_width=True
        )

    # Section 6: QA Report
    st.subheader("6. Final QA Report")
    orig_passed = sum(1 for r in orig_results if r["status"] == "PASS")
    fixed_passed = sum(1 for r in fixed_results if r["status"] == "PASS")
    total = len(test_cases)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Test Cases", total)
    m2.metric("Pre-Fix Passed", f"{orig_passed}/{total}")
    m3.metric("Post-Fix Passed", f"{fixed_passed}/{total}")
    m4.metric("Improvement", f"+{((fixed_passed - orig_passed)/total)*100:.0f}%" if total > 0 else "0%")

    if fixed_passed == total:
        st.balloons()
        st.success("🎉 All functional, boundary, and edge test cases passed against the rectified code!")
