# My Learning Adventure

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```
Default parent PIN: `2468`. Change it immediately.

## Deploy
Push this folder to a private GitHub repository and deploy `app.py` on Streamlit Community Cloud.

## Important
Version 1 uses SQLite and local uploads in `data/`. This works well on your computer. Free cloud local storage may be reset during restarts or redeployment. For multi-year persistence, the next version should use persistent Postgres/storage such as Supabase. Do not upload IDs, addresses, medical data, other children's faces, or book scans you are not permitted to use. Adult supervision is recommended.
