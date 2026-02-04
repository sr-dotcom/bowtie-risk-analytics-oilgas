import streamlit as st
from pathlib import Path
from src.app.utils import load_data

# Configuration
st.set_page_config(page_title="Bowtie Risk Analytics", layout="wide")
BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"


def render_incident_details(incident):
    st.subheader(f"{incident['incident_id']}: {incident['title']}")

    col_a, col_b = st.columns([1, 2])

    with col_a:
        st.markdown("**Description**")
        st.info(incident['description'])

        st.markdown("**Metadata**")
        st.json({
            "Date": incident['date'],
            "Location": incident['location'],
            "Potential Severity": incident['potential_severity']
        })

    with col_b:
        if "analytics" in incident:
            st.markdown("### Barrier Analysis")

            # Coverage
            cov = incident['analytics']['coverage']
            c1, c2 = st.columns(2)
            c1.metric("Prevention", f"{cov['prevention_coverage']:.1%}")
            c2.metric("Mitigation", f"{cov['mitigation_coverage']:.1%}")

            # Gaps
            gaps = incident['analytics']['gaps']
            if gaps:
                st.warning(f"⚠️ {len(gaps)} Barrier Gaps Detected")
                for gap in gaps:
                    with st.expander(f"{gap['type'].title()}: {gap['missing_barrier_id']}"):
                        st.write(f"**Description:** {gap['description']}")
            else:
                st.success("✅ No Barrier Gaps Detected")


def main():
    st.title("🛡️ Bowtie Risk Analytics")

    # Load Data
    with st.spinner("Loading data..."):
        incidents, metrics = load_data(PROCESSED_DIR)

    st.sidebar.success(f"Loaded {len(incidents)} incidents")

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Incidents", metrics.get("total_incidents", 0))
    col2.metric("Avg Prevention", f"{metrics.get('average_prevention_coverage', 0):.1%}")
    col3.metric("Avg Mitigation", f"{metrics.get('average_mitigation_coverage', 0):.1%}")
    col4.metric("Overall Coverage", f"{metrics.get('average_overall_coverage', 0):.1%}")

    st.divider()

    # Incident Explorer
    st.header("Incident Explorer")

    if not incidents:
        st.warning("No incidents found.")
        return

    # Selection
    selected_id = st.selectbox(
        "Select Incident",
        options=[i['incident_id'] for i in incidents],
        format_func=lambda x: next((f"{i['incident_id']} - {i['title']}" for i in incidents if i['incident_id'] == x), x)
    )

    selected_incident = next((i for i in incidents if i['incident_id'] == selected_id), None)

    if selected_incident:
        render_incident_details(selected_incident)


if __name__ == "__main__":
    main()
