from fastapi import HTTPException
from database import get_db_connection

class ProjectService:
    @staticmethod
    def create_project(project):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, first_name, last_name, company_id FROM users WHERE id = %s", (project.client_id,))
                client = cursor.fetchone()
                if not client:
                    raise HTTPException(status_code=400, detail="Invalid client_id. User does not exist.")
                
                company_id = client.get('company_id')
                company_name = None
                if company_id:
                    cursor.execute("SELECT company_name FROM companies WHERE id = %s", (company_id,))
                    company_row = cursor.fetchone()
                    if company_row:
                        company_name = company_row['company_name']

                cursor.execute("SELECT id FROM projects WHERE name = %s", (project.name,))
                if cursor.fetchone():
                    raise HTTPException(status_code=400, detail="Project with this name already exists")
                
                cursor.execute("INSERT INTO projects (name, client_id, project_type, company_id) VALUES (%s, %s, %s, %s)", (project.name, project.client_id, project.project_type, company_id))
                conn.commit()
                new_id = cursor.lastrowid
                
                client_name = f"{client['first_name']} {client['last_name']}".strip()
                return {
                    "id": new_id, 
                    "name": project.name, 
                    "client_id": project.client_id, 
                    "project_type": project.project_type,
                    "client_name": client_name,
                    "company_id": company_id,
                    "company_name": company_name,
                    "ticket_count": 0,
                    "ticket_titles": []
                }
        except HTTPException:
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def get_all_projects(current_user_id: int = None):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:   # ensure dictionary cursor
                cursor.execute("""
                    SELECT
                        p.id,
                        p.name,
                        p.project_type,
                        p.client_id,
                        u.first_name,
                        u.last_name,
                        p.company_id,
                        c.company_name,
                        COUNT(t.id) AS ticket_count,
                        GROUP_CONCAT(t.title SEPARATOR '|') AS ticket_titles
                    FROM projects p
                    LEFT JOIN users u ON p.client_id = u.id
                    LEFT JOIN companies c ON p.company_id = c.id
                    LEFT JOIN tickets t ON t.project_id = p.id
                    GROUP BY p.id, p.name, p.client_id, u.first_name, u.last_name, p.company_id, c.company_name
                    ORDER BY p.id DESC
                """)
                results = cursor.fetchall()
                watchlist_ids = set()
                if current_user_id:
                    cursor.execute("SELECT project_id FROM user_watchlist WHERE user_id = %s", (current_user_id,))
                    watchlist_ids = {row['project_id'] for row in cursor.fetchall()}
                projects = []
                for row in results:
                    # Build client name
                    client_name = None
                    if row['first_name'] or row['last_name']:
                        client_name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()

                    # Convert the pipe‑separated string into a Python list
                    ticket_titles = []
                    if row['ticket_titles']:
                        ticket_titles = row['ticket_titles'].split('|')

                    projects.append({
                        "id": row['id'],
                        "name": row['name'],
                        "client_id": row['client_id'],
                        "project_type": row['project_type'],
                        "client_name": client_name,
                        "company_id": row['company_id'],
                        "company_name": row['company_name'],
                        "ticket_count": row['ticket_count'],
                        "ticket_titles": ticket_titles,   # always a list
                        "in_watchlist": row['id'] in watchlist_ids
                    })
                return projects
        except Exception as e:
            # Log the full error for debugging
            print(f"Error in get_all_projects: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()


    @staticmethod
    def get_project(project_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        p.id, 
                        p.name,
                        p.project_type,
                        p.client_id, 
                        u.first_name, 
                        u.last_name,
                        p.company_id,
                        c.company_name,
                        COUNT(t.id) AS ticket_count,
                        GROUP_CONCAT(t.title SEPARATOR '|') AS ticket_titles
                    FROM projects p 
                    LEFT JOIN users u ON p.client_id = u.id 
                    LEFT JOIN companies c ON p.company_id = c.id
                    LEFT JOIN tickets t ON t.project_id = p.id
                    WHERE p.id = %s
                    GROUP BY p.id, p.name, p.client_id, u.first_name, u.last_name, p.company_id, c.company_name
                """, (project_id,))
                row = cursor.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Project not found")
                
                client_name = None
                if row['first_name'] or row['last_name']:
                    client_name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
                
                ticket_titles = []
                if row['ticket_titles']:
                    ticket_titles = row['ticket_titles'].split('|')
                    
                return {
                    "id": row['id'],
                    "name": row['name'],
                    "client_id": row['client_id'],
                    "project_type": row['project_type'],
                    "client_name": client_name,
                    "company_id": row['company_id'],
                    "company_name": row['company_name'],
                    "ticket_count": row['ticket_count'],
                    "ticket_titles": ticket_titles
                }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def update_project(project_id: int, project):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
                if not cursor.fetchone():
                    raise HTTPException(status_code=404, detail="Project not found")
                    
                cursor.execute("SELECT id, first_name, last_name, company_id FROM users WHERE id = %s", (project.client_id,))
                client = cursor.fetchone()
                if not client:
                    raise HTTPException(status_code=400, detail="Invalid client_id. User does not exist.")
                
                company_id = client.get('company_id')
                company_name = None
                if company_id:
                    cursor.execute("SELECT company_name FROM companies WHERE id = %s", (company_id,))
                    company_row = cursor.fetchone()
                    if company_row:
                        company_name = company_row['company_name']

                cursor.execute("SELECT id FROM projects WHERE name = %s AND id != %s", (project.name, project_id))
                if cursor.fetchone():
                    raise HTTPException(status_code=400, detail="Another project with this name already exists")
                
                cursor.execute("UPDATE projects SET name = %s, client_id = %s, project_type = %s, company_id = %s WHERE id = %s", (project.name, project.client_id, project.project_type, company_id, project_id))
                conn.commit()
                
                client_name = f"{client['first_name']} {client['last_name']}".strip()
                
                # Fetch updated stats
                cursor.execute("SELECT COUNT(id) FROM tickets WHERE project_id = %s", (project_id,))
                ticket_count = cursor.fetchone()['COUNT(id)']
                
                cursor.execute("SELECT title FROM tickets WHERE project_id = %s", (project_id,))
                ticket_titles = [t['title'] for t in cursor.fetchall()]

                return {
                    "id": project_id, 
                    "name": project.name, 
                    "client_id": project.client_id, 
                    "project_type": project.project_type,
                    "client_name": client_name,
                    "company_id": company_id,
                    "company_name": company_name,
                    "ticket_count": ticket_count,
                    "ticket_titles": ticket_titles
                }
        except HTTPException:
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def delete_project(project_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
                if not cursor.fetchone():
                    raise HTTPException(status_code=404, detail="Project not found")
                
                cursor.execute("DELETE FROM projects WHERE id = %s", (project_id,))
                conn.commit()
                return True
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def add_to_watchlist(project_id: int, user_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
                if not cursor.fetchone():
                    raise HTTPException(status_code=404, detail="Project not found")
                
                cursor.execute("SELECT id FROM user_watchlist WHERE user_id = %s AND project_id = %s", (user_id, project_id))
                if cursor.fetchone():
                    return {"message": "Project already in watchlist"}
                
                cursor.execute("INSERT INTO user_watchlist (user_id, project_id) VALUES (%s, %s)", (user_id, project_id))
                conn.commit()
                return {"message": "Project added to watchlist"}
        except HTTPException:
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

    @staticmethod
    def remove_from_watchlist(project_id: int, user_id: int):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM user_watchlist WHERE user_id = %s AND project_id = %s", (user_id, project_id))
                conn.commit()
                return {"message": "Project removed from watchlist"}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()
