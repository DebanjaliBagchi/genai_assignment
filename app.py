import streamlit as st
import json
import ast
import traceback
from typing import List, Dict, Any

# ==========================================
# PAGE CONFIGURATION & STYLING
# ==========================================
st.set_page_config(
    page_title="AI-Powered Code Rectifier & Testing Assistant",
    page_icon="🛠️",
    layout="wide"
)

st.title("🛠️ AI-Powered Code Rectifier and Testing Assistant")
st.markdown("Automated Bug Detection, Code Rectification, Test Case Generation, and Dynamic Test Execution.")
st.divider()

# ==========================================
# SIDEBAR CONFIGURATION
# ==========================================
st.sidebar.header("⚙️ Configuration")
api_choice = st.sidebar.selectbox("LLM Mode", ["Mock Engine (No API Key Required)", "OpenAI GPT-4o-mini"])
api_key = ""
if api_choice == "OpenAI GPT-4o-mini":
    api_key = st.sidebar.text_input("Enter OpenAI API Key", type="password")

# ==========================================
# DEFAULT FAULTY CODE (FROM SPECIFICATION)
# ==========================================
DEFAULT_CODE = '''def calculate_average(numbers):
    total = 0
    
    for i in range(len(numbers) + 1):
        total += numbers[i]
        
    return total / len(numbers)

numbers = [10, 20, 30, 40]
print(calculate_average(numbers))
'''

# Mandatory test cases from specification
MANDATORY_TESTS = [
    {"id": "TC01", "name": "Standard List", "input": [10, 20, 30], "expected": 20.0},
    {"id": "TC02", "name": "Single Element", "input": [5], "expected": 5.0},
    {"id": "TC03", "name": "Empty List", "input": [], "expected": 0.0},  # or None / handled safely
    {"id": "TC04", "name": "Negative & Positive", "input": [-10, 10], "expected": 0.0},
    {"id": "TC05", "name": "Sequential Ints", "input": [1, 2, 3, 4], "expected": 2.5},
]

# ==========================================
# CORE AI / ANALYSIS ENGINES
# ==========================================
def analyze_and_rectify_mock(code: str) -> Dict[str, Any]:
    """Fallback engine replicating exact LLM output without external API."""
    return {
        "bugs": [
            {
                "type": "Off-by-one Error",
                "location": "range(len(numbers) + 1)",
                "explanation": "Iterating up to len(numbers) + 1 causes an IndexError because valid list indices are 0 to len - 1."
            },
            {
                "type": "Division by Zero",
                "location": "total / len(numbers)",
                "explanation": "Passing an empty list [] results in len(numbers) == 0, triggering an unhandled ZeroDivisionError."
            },
            {
                "type": "Lack of Input Validation",
                "location": "Function parameter",
                "explanation": "The function does not verify if the input is a valid iterable or if it contains non-numeric data."
            }
        ],
        "rectified_code": '''def calculate_average(numbers):
    """Calculates the average of a list of numbers with defensive checks."""
    if not isinstance(numbers, (list, tuple)):
        raise TypeError("Input must be a list or tuple")
    if len(numbers) == 0:
        return 0.0
    
    total = 0
    for num in numbers:
        total += num
        
    return total / len(numbers)
''',
        "additional_edge_cases": [
            {"id": "TC06", "name": "Edge: Floating Points", "input": [1.5, 2.5, 3.5], "expected": 2.5},
            {"id": "TC07", "name": "Edge: Large Numbers", "input": [1000000, 2000000], "expected": 1500000.0}
        ]
    }

def analyze_and_rectify_openai(code: str, key: str) -> Dict[str, Any]:
    """Calls OpenAI API to identify bugs, rectify code, and generate test cases."""
    from openai import OpenAI
    client = OpenAI(api_key=key)
    
    prompt = f"""
    Analyze the following Python code for bugs and security/edge-case issues:
    ```python
    {code}
    ```
    Return a strictly formatted JSON object with this exact structure:
    {{
      "bugs": [
        {{"type": "error title", "location": "code line", "explanation": "detailed explanation"}}
      ],
      "rectified_code": "def calculate_average(numbers): ... (valid clean python function only)",
      "additional_edge_cases": [
        {{"id": "TC06", "name": "description", "input": [1.5, 2.5], "expected": 2.0}}
      ]
    }}
    Ensure the rectified code handles empty lists (returning 0.0) and validates inputs.
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

# ==========================================
# DYNAMIC TEST EXECUTION ENGINE
# ==========================================
def execute_tests(function_code: str, test_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Dynamically compiles the rectified code in a safe scope and runs test cases."""
    results = []
    
    # Create isolated execution scope
    local_scope = {}
    try:
        exec(function_code, {}, local_scope)
    except Exception as e:
        for tc in test_cases:
            results.append({
                **tc,
                "actual": "Compilation Error",
                "status": "FAIL",
                "error": str(e)
            })
        return results

    func = local_scope.get("calculate_average")
    if not func:
        for tc in test_cases:
            results.append({
                **tc,
                "actual": "Function Not Found",
                "status": "FAIL",
                "error": "calculate_average function definition missing"
            })
        return results

    for tc in test_cases:
        try:
            actual_val = func(tc["input"])
            # Compare floating values with tolerance
            if isinstance(actual_val, (int, float)) and isinstance(tc["expected"], (int, float)):
                passed = abs(actual_val - tc["expected"]) < 1e-6
            else:
                passed = actual_val == tc["expected"]
                
            results.append({
                "id": tc["id"],
                "name": tc["name"],
                "input": str(tc["input"]),
                "expected": str(tc["expected"]),
                "actual": str(actual_val),
                "status": "PASS" if passed else "FAIL",
                "error": None
            })
        except Exception as e:
            results.append({
                "id": tc["id"],
                "name": tc["name"],
                "input": str(tc["input"]),
                "expected": str(tc["expected"]),
                "actual": "Runtime Error",
                "status": "FAIL",
                "error": str(e)
            })
            
    return results

# ==========================================
# USER INTERFACE - 6 SECTIONS
# ==========================================

# 1. Code Input
st.subheader("1. Code Input")
user_code = st.text_area(
    "Submit Faulty Python Code:",
    value=DEFAULT_CODE,
    height=200,
    help="Enter the Python function to be analyzed and rectified."
)

start_analysis = st.button("🚀 Analyze, Rectify & Run Tests", type="primary")

if start_analysis:
    with st.spinner("Analyzing code, rectifying implementation, and synthesizing test suites..."):
        try:
            if api_choice == "OpenAI GPT-4o-mini" and api_key:
                ai_data = analyze_and_rectify_openai(user_code, api_key)
            else:
                ai_data = analyze_and_rectify_mock(user_code)
        except Exception as e:
            st.error(f"Error during AI analysis: {str(e)}")
            st.stop()

    col1, col2 = st.columns(2)

    # 2. Bug Analysis
    with col1:
        st.subheader("2. Bug Analysis")
        for i, bug in enumerate(ai_data.get("bugs", []), 1):
            with st.expander(f"⚠️ Bug {i}: {bug['type']}", expanded=True):
                st.markdown(f"**Identified At:** `{bug['location']}`")
                st.write(bug['explanation'])

    # 3. Corrected Code
    with col2:
        st.subheader("3. Corrected Python Code")
        rectified = ai_data.get("rectified_code", "")
        st.code(rectified, language="python")

    # Combine mandatory test cases with AI-generated edge cases
    all_test_cases = MANDATORY_TESTS + ai_data.get("additional_edge_cases", [])

    # 4. Test Case Generation
    st.subheader("4. Generated Test Cases (Mandatory + AI Edge Cases)")
    tc_display = [
        {"Test ID": tc["id"], "Scenario": tc["name"], "Input": str(tc["input"]), "Expected Output": str(tc["expected"])}
        for tc in all_test_cases
    ]
    st.table(tc_display)

    # 5. Dynamic Execution & Results
    st.subheader("5. Test Execution Results")
    test_results = execute_tests(rectified, all_test_cases)
    
    # Format table for results
    formatted_results = []
    passed_count = 0
    for r in test_results:
        is_pass = r["status"] == "PASS"
        if is_pass:
            passed_count += 1
        formatted_results.append({
            "Test ID": r["id"],
            "Scenario": r["name"],
            "Input": r["input"],
            "Expected": r["expected"],
            "Actual": r["actual"],
            "Status": "✅ PASS" if is_pass else "❌ FAIL"
        })
    st.dataframe(formatted_results, use_container_width=True)

    # 6. Final Report
    st.subheader("6. Final Testing Summary Report")
    total_tests = len(test_results)
    failed_count = total_tests - passed_count
    pass_rate = (passed_count / total_tests) * 100

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("Total Tests Executed", total_tests)
    col_m2.metric("Tests Passed", passed_count)
    col_m3.metric("Tests Failed", failed_count)
    col_m4.metric("Pass Rate", f"{pass_rate:.1f}%")

    if failed_count == 0:
        st.success("🎉 All test cases (functional, boundary, and edge cases) passed successfully against the rectified code!")
    else:
        st.warning(f"{failed_count} test case(s) failed. Review edge conditions and assertions.")
