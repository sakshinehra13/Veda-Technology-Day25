import requests
import streamlit as st

st.set_page_config(page_title="Resilient API & Retry Dashboard", page_icon="⚡", layout="wide")

st.title("⚡ Resilient API & Timeout Management System")
st.markdown("An interactive system implementing **request timeouts, retries, exponential backoff, and selective error handling**.")

# Sidebar Configurations
st.sidebar.header("⚙️ Client Configuration")
timeout_val = st.sidebar.slider("Request Timeout (sec)", min_value=0.5, max_value=10.0, value=2.0, step=0.5)
max_retries = st.sidebar.slider("Max Retries", min_value=0, max_value=5, value=3)
backoff_factor = st.sidebar.slider("Backoff Multiplier Factor", min_value=0.5, max_value=3.0, value=1.0, step=0.5)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Select Test Scenario")
scenario = st.sidebar.selectbox(
    "Choose simulated backend behavior:",
    (
        "Intermittent Server Error (500 -> Recovers)",
        "Timeout / Slow Response (Hangs)",
        "Permanent Client Error (404 Not Found)",
        "External URL (e.g., httpbin)"
    )
)

# Determine Target URL based on scenario
BASE_BACKEND = "http://127.0.0.1:8000"
target_url = ""

if scenario == "Intermittent Server Error (500 -> Recovers)":
    fail_count = st.sidebar.number_input("Failures before success", min_value=1, max_value=4, value=2)
    target_url = f"{BASE_BACKEND}/mock/unstable?fail_count={fail_count}"
    st.info(f"Targeting mock server that will fail **{fail_count} times** with HTTP 500, then succeed. Watch exponential backoff kick in!")

elif scenario == "Timeout / Slow Response (Hangs)":
    delay = st.sidebar.slider("Server response delay (sec)", min_value=1, max_value=8, value=4)
    target_url = f"{BASE_BACKEND}/mock/timeout?delay={delay}"
    st.info(f"Targeting a slow endpoint taking **{delay}s** to respond while your client timeout is set to **{timeout_val}s**. This will force a timeout exception!")

elif scenario == "Permanent Client Error (404 Not Found)":
    target_url = f"{BASE_BACKEND}/mock/client-error"
    st.info("Targeting an endpoint throwing an HTTP 404. Notice how the system **fails fast** without wasting retries.")

elif scenario == "External URL (e.g., httpbin)":
    target_url = st.text_input("Custom URL", "https://httpbin.org/get")
    st.info("Querying a live public testing API.")

# Execute Request Button
if st.button("🚀 Fire API Request with Resilient Client", type="primary"):
    with st.spinner("Executing request pipeline with retry logic..."):
        try:
            # Call our backend client executor route
            resp = requests.get(
                f"{BASE_BACKEND}/api/test-client",
                params={
                    "target_url": target_url,
                    "timeout": timeout_val,
                    "max_retries": max_retries,
                    "backoff_factor": backoff_factor
                }
            )
            result = resp.json()
            
            # Metrics Display
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="Operation Outcome", value="SUCCESS" if result["success"] else "FAILED")
            with col2:
                st.metric(label="Final Status Code", value=result.get("status_code", "N/A"))
            with col3:
                st.metric(label="Total Logged Steps", value=len(result.get("logs", [])))

            # Tabs for Detailed Analysis
            tab1, tab2 = st.tabs(["📋 Execution Logs & Backoff Timeline", "📦 Raw Response Payload"])
            
            with tab1:
                st.markdown("### Step-by-Step Backoff & Trace Logs")
                for log in result.get("logs", []):
                    status = log.get("status")
                    if status == "Success":
                        st.success(f"**Attempt {log['attempt']}**: {log['message']}")
                    elif status == "Retry Backoff":
                        st.warning(f"**Attempt {log['attempt']}**: {log['message']}")
                    elif "Error" in status or status == "Failed":
                        st.error(f"**Attempt {log.get('attempt', max_retries)}**: {log['message']}")
                    else:
                        st.info(f"**Attempt {log['attempt']}**: {log['message']}")

            with tab2:
                st.json(result)

        except requests.exceptions.ConnectionError:
            st.error("❌ Could not connect to the local FastAPI backend. Make sure you started it with `uvicorn app:app --reload`!")