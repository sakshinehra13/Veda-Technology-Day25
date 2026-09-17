import time
import logging
import requests
import streamlit as st
from requests.exceptions import RequestException, Timeout

# Configure page
st.set_page_config(page_title="Resilient API & Retry Dashboard", page_icon="⚡", layout="wide")

st.title("⚡ Resilient API & Timeout Management System")
st.markdown("An interactive system implementing **request timeouts, retries, exponential backoff, and selective error handling**.")

# --- 1. CORE RESILIENT API CLIENT LOGIC ---
class ResilientAPIClient:
    def __init__(self, default_timeout=3.0, max_retries=3, backoff_factor=1.0):
        self.default_timeout = default_timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.session = requests.Session()

    def make_request(self, method, url, timeout=None, **kwargs):
        timeout = timeout or self.default_timeout
        retries = 0
        logs = []

        while retries <= self.max_retries:
            attempt_msg = f"Attempt {retries + 1}/{self.max_retries + 1} - Calling {method.upper()} {url}"
            logs.append({"attempt": retries + 1, "status": "Attempting", "message": attempt_msg})
            
            start_time = time.time()
            try:
                response = self.session.request(method, url, timeout=timeout, **kwargs)
                elapsed = round(time.time() - start_time, 2)
                
                # Check for server errors or rate limiting to trigger a retry
                if 500 <= response.status_code < 600 or response.status_code == 429:
                    warn_msg = f"Server returned error code {response.status_code}. Retrying..."
                    logs.append({"attempt": retries + 1, "status": "Warning", "message": warn_msg})
                    response.raise_for_status()

                success_msg = f"Success! Status code: {response.status_code} (Time: {elapsed}s)"
                logs.append({"attempt": retries + 1, "status": "Success", "message": success_msg})
                return {"success": True, "status_code": response.status_code, "data": response.text, "logs": logs}

            except (Timeout, RequestException) as e:
                # Do not retry standard client errors (400-499 except 429)
                if hasattr(e, 'response') and e.response is not None:
                    sc = e.response.status_code
                    if 400 <= sc < 500 and sc != 429:
                        err_msg = f"Client Error {sc} encountered. Aborting retries immediately."
                        logs.append({"attempt": retries + 1, "status": "Fatal Client Error", "message": err_msg})
                        return {"success": False, "status_code": sc, "error": str(e), "logs": logs}

                retries += 1
                if retries > self.max_retries:
                    err_msg = f"Max retries ({self.max_retries}) exceeded. Operation failed."
                    logs.append({"attempt": retries, "status": "Failed", "message": err_msg})
                    return {"success": False, "status_code": 504, "error": str(e), "logs": logs}

                # Exponential backoff formula
                sleep_time = self.backoff_factor * (2 ** (retries - 1))
                sleep_msg = f"Request failed ({str(e)}). Backing off for {sleep_time}s..."
                logs.append({"attempt": retries, "status": "Retry Backoff", "message": sleep_msg, "sleep_time": sleep_time})
                time.sleep(sleep_time)

# --- Sidebar Configurations ---
st.sidebar.header("⚙️ Client Configuration")
timeout_val = st.sidebar.slider("Request Timeout (sec)", min_value=0.5, max_value=10.0, value=2.0, step=0.5)
max_retries = st.sidebar.slider("Max Retries", min_value=0, max_value=5, value=3)
backoff_factor = st.sidebar.slider("Backoff Multiplier Factor", min_value=0.5, max_value=3.0, value=1.0, step=0.5)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Select Test Scenario")
scenario = st.sidebar.selectbox(
    "Choose test behavior:",
    (
        "Public API Success (httpbin)",
        "Timeout Simulation (Request to non-routable IP)",
        "Client Error Simulation (404 Not Found)"
    )
)

# Target URL mapping
if scenario == "Public API Success (httpbin)":
    target_url = "https://httpbin.org/get"
    st.info("Testing with a reliable public API endpoint.")
elif scenario == "Timeout Simulation (Request to non-routable IP)":
    target_url = "http://10.255.255.1"  # Non-routable IP causes a guaranteed timeout/hang
    st.info(f"Targeting a dead IP address with a **{timeout_val}s** timeout to test timeout handling and retries.")
elif scenario == "Client Error Simulation (404 Not Found)":
    target_url = "https://httpbin.org/status/404"
    st.info("Targeting an endpoint returning HTTP 404. Notice how it fails fast without retrying.")

# Execute Request Button
if st.button("🚀 Fire API Request with Resilient Client", type="primary"):
    with st.spinner("Executing request pipeline with retry logic..."):
        client = ResilientAPIClient(default_timeout=timeout_val, max_retries=max_retries, backoff_factor=backoff_factor)
        result = client.make_request("GET", target_url)
        
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