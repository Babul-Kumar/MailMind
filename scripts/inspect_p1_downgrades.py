import pandas as pd

df = pd.read_csv('dataset-v4.1/production_priority_changes.csv')
p1_down = df[(df['v3_priority'] == 'P1') & (df['v4_1_priority'] != 'P1')].copy()

print(f"Total P1 -> lower transitions: {len(p1_down)}")
print("-" * 80)
for i, (_, r) in enumerate(p1_down.iterrows()):
    subj = str(r['subject'])
    print(f"{i+1:02d}. [{r['message_id']}] v3: {r['v3_priority']} -> v4.1: {r['v4_1_priority']} (v4: {r['v4_priority']}) | Act: {r['action_required']} | Subj: {subj[:65]}")

import sqlite3
conn = sqlite3.connect('google_auth/cache/mailmind_cache.db')
c = conn.cursor()
c.execute('SELECT snippet, body FROM user_email_cache WHERE message_id = ?', ('1a03093473dd7d0a',))
row = c.fetchone()
print("\n--- 1a03093473dd7d0a Content ---")
print("Snippet:", row[0])
print("Body:", (row[1] or "")[:300])
conn.close()
