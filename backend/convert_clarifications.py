import sqlite3

def run():
    conn = sqlite3.connect('backend/app.db')
    c = conn.cursor()
    c.execute("""
        UPDATE bills 
        SET status = 'READY_FOR_APPROVAL', is_gst_detected = 0 
        WHERE status = 'CLARIFICATION_REQUIRED' OR is_gst_detected = 1
    """)
    print(f"Updated {c.rowcount} bills to READY_FOR_APPROVAL")
    conn.commit()

    # Also check counts by status
    c.execute("SELECT status, count(*) FROM bills GROUP BY status")
    for row in c.fetchall():
        print(f"Status '{row[0]}': {row[1]} bills")

    conn.close()

if __name__ == '__main__':
    run()

