from fastapi import HTTPException

class DepartmentService:
    @staticmethod
    def create_department(dept, db):
        with db.cursor() as cursor:
            cursor.execute("SELECT id FROM departments WHERE name=%s", (dept.name,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Department already exists")
                
            sql = "INSERT INTO departments (name,parent_department_id ) VALUES (%s,%s)"
            cursor.execute(sql, (dept.name, dept.parent_department_id))
            db.commit()
            last_id = cursor.lastrowid
            
            cursor.execute("SELECT id, name FROM departments WHERE id=%s", (last_id,))
            new_dept = cursor.fetchone()
            
            return new_dept

    @staticmethod
    def get_department_hierarchy(db):
        with db.cursor() as cursor:
            cursor.execute("SELECT id, name, parent_department_id FROM departments ORDER BY id")
            all_depts = cursor.fetchall()

            children = {}
            for dept in all_depts:
                parent_id = dept.get("parent_department_id")
                if parent_id is not None:
                    children.setdefault(parent_id, []).append(dept)

            def build_node(dept):
                node = {
                    "id": dept["id"],
                    "name": dept["name"],
                    "data": []
                }
                for child in children.get(dept["id"], []):
                    node["data"].append(build_node(child))
                return node

            all_ids = {d["id"] for d in all_depts}
            roots = [
                d for d in all_depts 
                if d.get("parent_department_id") is None or d.get("parent_department_id") not in all_ids
            ]

            hierarchy = [build_node(root) for root in roots]
            return hierarchy

    @staticmethod
    def get_all_departments(db):
        with db.cursor() as cursor:
            cursor.execute("SELECT id, name,parent_department_id FROM departments ORDER BY id DESC")
            departments = cursor.fetchall()
            return departments

    @staticmethod
    def get_department(dept_id: int, db):
        with db.cursor() as cursor:
            cursor.execute("SELECT id, name , parent_department_id FROM departments WHERE id=%s", (dept_id,))
            dept = cursor.fetchone()
            if not dept:
                raise HTTPException(status_code=404, detail="Department not found")
            return dept

    @staticmethod
    def update_department(dept_id: int, dept_update, db):
        with db.cursor() as cursor:
            cursor.execute("SELECT id FROM departments WHERE id=%s", (dept_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Department not found")
                
            sql = "UPDATE departments SET name = %s, parent_department_id = %s WHERE id = %s"
            cursor.execute(sql, (dept_update.name, dept_update.parent_department_id, dept_id))
            db.commit()
            
            cursor.execute("SELECT id, name ,parent_department_id FROM departments WHERE id=%s", (dept_id,))
            updated_dept = cursor.fetchone()
            return updated_dept

    @staticmethod
    def delete_department(dept_id: int, db):
        with db.cursor() as cursor:
            cursor.execute("SELECT id FROM departments WHERE id=%s", (dept_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Department not found")
                
            cursor.execute("DELETE FROM departments WHERE id=%s", (dept_id,))
            db.commit()
            return True
