from fastapi import HTTPException


class RoleService:
    @staticmethod
    def get_all_roles(db):
        with db.cursor() as cursor:
            cursor.execute("SELECT id, name FROM roles ORDER BY id DESC")
            return cursor.fetchall()

    @staticmethod
    def get_role_by_id(role_id: int, db):
        with db.cursor() as cursor:
            cursor.execute("SELECT id, name FROM roles WHERE id=%s", (role_id,))
            role = cursor.fetchone()
            if not role:
                raise HTTPException(status_code=404, detail="Role not found")

            permissions = RoleService.build_permissions_matrix(role_id, db)
            return {
                "id": role["id"],
                "name": role["name"],
                "rolesActions": permissions,
            }

    @staticmethod
    def get_all_actions(db):
        with db.cursor() as cursor:
            cursor.execute("SELECT id, name FROM actions ORDER BY id")
            return cursor.fetchall()

    @staticmethod
    def get_permissions_matrix(role_id: int, db):
        """Return the permissions matrix for a given role.
        If role_id is 0, return a blank template (roleAssignedActions=[])."""
        return RoleService.build_permissions_matrix(role_id, db)

    @staticmethod
    def build_permissions_matrix(role_id: int, db):
        with db.cursor() as cursor:
            # Get all functionalities
            cursor.execute("SELECT id, name FROM functionalities ORDER BY id")
            functionalities = cursor.fetchall()

            # Get all modules
            cursor.execute("SELECT id, functionality_id, name FROM modules ORDER BY id")
            all_modules = cursor.fetchall()

            # Get all module_actions (moduleAssignedActions)
            cursor.execute("SELECT id, module_id, action_id FROM modules_actions")
            all_module_actions = cursor.fetchall()

            # Get role's assigned actions (via role_module_actions)
            role_assigned = []
            if role_id and role_id > 0:
                cursor.execute(
                    """
                    SELECT rma.module_action_id, ma.module_id, ma.action_id
                    FROM role_module_actions rma
                    JOIN modules_actions ma ON ma.id = rma.module_action_id
                    WHERE rma.role_id = %s
                    """,
                    (role_id,),
                )
                role_assigned = cursor.fetchall()

            # Build lookup: module_id -> set of role-assigned action_ids
            role_action_map = {}
            for ra in role_assigned:
                mid = ra["module_id"]
                if mid not in role_action_map:
                    role_action_map[mid] = set()
                role_action_map[mid].add(ra["action_id"])

            # Build lookup: module_id -> list of assigned action_ids (from modules_actions)
            module_action_map = {}
            for ma in all_module_actions:
                mid = ma["module_id"]
                if mid not in module_action_map:
                    module_action_map[mid] = []
                module_action_map[mid].append(ma["action_id"])

            result = []
            for func in functionalities:
                func_modules = [m for m in all_modules if m["functionality_id"] == func["id"]]
                modules_list = []
                for mod in func_modules:
                    module_assigned_actions = sorted(module_action_map.get(mod["id"], []))
                    role_assigned_actions = sorted(list(role_action_map.get(mod["id"], set())))
                    modules_list.append(
                        {
                            "moduleId": mod["id"],
                            "moduleName": mod["name"],
                            "moduleAssignedActions": module_assigned_actions,
                            "roleAssignedActions": role_assigned_actions,
                        }
                    )

                if modules_list:
                    result.append(
                        {
                            "functionalityId": func["id"],
                            "functionalityName": func["name"],
                            "modules": modules_list,
                        }
                    )

            return {"functionalities": result}

    @staticmethod
    def create_role(data: dict, db):
        name = data.get("name", "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Role name is required")

        with db.cursor() as cursor:
            # Check duplicate
            cursor.execute("SELECT id FROM roles WHERE name=%s", (name,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Role name already exists")

            # Insert role
            cursor.execute("INSERT INTO roles (name) VALUES (%s)", (name,))
            db.commit()
            role_id = cursor.lastrowid

            # Save permissions
            RoleService._save_role_permissions(role_id, data, cursor)
            db.commit()

            return {"id": role_id, "name": name}

    @staticmethod
    def update_role(role_id: int, data: dict, db):
        name = data.get("name", "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Role name is required")

        with db.cursor() as cursor:
            # Check role exists
            cursor.execute("SELECT id FROM roles WHERE id=%s", (role_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Role not found")

            # Check duplicate name (exclude self)
            cursor.execute(
                "SELECT id FROM roles WHERE name=%s AND id != %s", (name, role_id)
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Role name already exists")

            # Update role name
            cursor.execute("UPDATE roles SET name=%s WHERE id=%s", (name, role_id))

            # Delete old permissions
            cursor.execute("DELETE FROM role_module_actions WHERE role_id=%s", (role_id,))

            # Save new permissions
            RoleService._save_role_permissions(role_id, data, cursor)
            db.commit()

            return {"id": role_id, "name": name}

    @staticmethod
    def _save_role_permissions(role_id: int, data: dict, cursor):
        """Insert role_module_actions rows from the incoming JSON."""
        roles_actions = data.get("rolesActions", {})
        functionalities = roles_actions.get("functionalities", [])

        for func in functionalities:
            for module in func.get("modules", []):
                module_id = module.get("moduleId")
                role_assigned = module.get("roleAssignedActions", [])
                for action_id in role_assigned:
                    # Lookup module_action_id from modules_actions
                    cursor.execute(
                        "SELECT id FROM modules_actions WHERE module_id=%s AND action_id=%s",
                        (module_id, action_id),
                    )
                    ma_row = cursor.fetchone()
                    if ma_row:
                        cursor.execute(
                            "INSERT IGNORE INTO role_module_actions (role_id, module_action_id) VALUES (%s, %s)",
                            (role_id, ma_row["id"]),
                        )

    @staticmethod
    def delete_role(role_id: int, db):
        with db.cursor() as cursor:
            cursor.execute("SELECT id FROM roles WHERE id=%s", (role_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Role not found")

            cursor.execute("DELETE FROM roles WHERE id=%s", (role_id,))
            db.commit()
            return True
