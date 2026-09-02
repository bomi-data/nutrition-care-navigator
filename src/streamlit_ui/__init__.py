"""UI-facing adapter layer for the Streamlit MVP.

This package contains NO recommendation logic. It only translates between
human-facing strings (Korean button/select labels) and the typed values
`src/recommender` already defines (TriState, DesiredSupport, UserProfile).

Streamlit code (app/streamlit_app.py) should only ever call functions from
here to build a UserProfile -- it must never import recommender.matcher /
filters / scorer directly, and it must never re-implement any matching or
scoring rule itself.
"""
