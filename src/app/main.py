import sys
import streamlit as st
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from src.app.utils import load_data

# Configuration
st.set_page_config(page_title="Bowtie Risk Analytics", layout="wide")
BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"


def render_incident_details(incident):
    title = incident.get('title', incident.get('description', 'No description')[:50])
    st.subheader(f"{incident['incident_id']}: {title}")

    col_a, col_b = st.columns([1, 2])

    with col_a:
        st.markdown("**Description**")
        st.info(incident.get('description', 'No description available'))

        st.markdown("**Metadata**")
        st.json({
            "Date": incident.get('date', 'Unknown'),
            "Location": incident.get('location') or 'Unknown',
            "Severity": incident.get('severity') or incident.get('potential_severity') or 'Unknown'
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
            gaps = incident['analytics'].get('gaps', [])
            if gaps:
                st.warning(f"⚠️ {len(gaps)} Barrier Gaps Detected")
                for gap in gaps:
                    gap_id = gap.get('missing_barrier_id') or gap.get('id', 'Unknown')
                    gap_name = gap.get('name', gap_id)
                    gap_type = gap.get('type', 'unknown').title()
                    with st.expander(f"{gap_type}: {gap_name}"):
                        st.write(f"**Description:** {gap.get('description', 'No description')}")
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
    def format_incident(incident_id):
        for i in incidents:
            if i['incident_id'] == incident_id:
                title = i.get('title', i.get('description', '')[:40])
                return f"{incident_id} - {title}"
        return incident_id

    selected_id = st.selectbox(
        "Select Incident",
        options=[i['incident_id'] for i in incidents],
        format_func=format_incident
    )

    selected_incident = next((i for i in incidents if i['incident_id'] == selected_id), None)

    if selected_incident:
        render_incident_details(selected_incident)


if __name__ == "__main__":
    main()
