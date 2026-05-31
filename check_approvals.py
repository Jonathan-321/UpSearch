import db; db.init_db()

with db.conn() as c:
    rows = c.execute("""
        SELECT m.id, m.variant, m.word_count, m.status,
               p.name as person, co.name as company
        FROM messages m
        LEFT JOIN people p ON m.person_id = p.id
        LEFT JOIN packets pk ON m.packet_id = pk.id
        LEFT JOIN companies co ON pk.company_id = co.id
        ORDER BY m.id
    """).fetchall()

approved = [r for r in rows if r["status"] == "approved"]
draft    = [r for r in rows if r["status"] == "draft"]

print(f"Total messages : {len(rows)}")
print(f"Approved       : {len(approved)}")
print(f"Still draft    : {len(draft)}")
print()
print("APPROVED:")
for r in approved:
    print(f"  #{r['id']:>2} | {(r['company'] or '?'):<12} | {r['variant']:<22} | {r['word_count']:>3}w | {r['person'] or '?'}")
