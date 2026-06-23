from fastapi import HTTPException

class SystemService:
    @staticmethod
    def get_navigation_menu(user_email: str, db):
        with db.cursor() as cursor:
            cursor.execute("SELECT id, role_id FROM users WHERE email=%s", (user_email,))
            user = cursor.fetchone()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
                
            role_id = user['role_id']
            
            sql = """
            SELECT f.id, f.name 
            FROM functionalities f
            """
            cursor.execute(sql)
            all_functionalities = cursor.fetchall()
    
            # Fetch all modules to map them to functionalities
            cursor.execute("SELECT id, functionality_id, name FROM modules")
            all_modules = cursor.fetchall()
            
            menu_items = []
            projects_items = []
            reports_items = []
            settings_items = []
    
            for func in all_functionalities:
                title = func['name'].title()
                if title == "Manage Reports":
                    path = "/dailyreport"
                else:
                    path = f"/{func['name'].replace(' ', '-')}"
    
                func_modules = [m['name'] for m in all_modules if m['functionality_id'] == func['id']]
                module_name = func_modules[0] if func_modules else ""
                
                item = {
                    "id": func['id'], 
                    "title": title, 
                    "path": path,
                    "permission": {
                        "functionality_name": func['name'],
                        "module_name": module_name,
                        "actions": [4]
                    }
                }
                
                if title in ["Manage Project", "Manage Tickets"]:
                    projects_items.append(item)
                elif title == "Manage Reports":
                    # Fetch modules for reports functionality (id 14)
                    cursor.execute("SELECT id, name FROM modules WHERE functionality_id = %s", (func['id'],))
                    report_modules = cursor.fetchall()
                    for r_mod in report_modules:
                        # Check permission for this specific module
                        cursor.execute("""
                            SELECT COUNT(*) as cnt
                            FROM role_module_actions rma
                            JOIN modules_actions ma ON rma.module_action_id = ma.id
                            WHERE rma.role_id = %s AND ma.module_id = %s AND ma.action_id = 4
                        """, (role_id, r_mod['id']))
                        has_perm = cursor.fetchone()['cnt'] > 0 or role_id == 1
                        if has_perm:
                            path_name = "/dailyreport" if r_mod['name'] == "Daily Report" else "/monthlyreport"
                            reports_items.append({
                                "id": f"report-{r_mod['id']}",
                                "title": r_mod['name'],
                                "path": path_name,
                                "permission": {
                                    "functionality_name": func['name'],
                                    "module_name": r_mod['name'],
                                    "actions": [4]
                                }
                            })
                else:
                    settings_items.append(item)
            
            # Always add the root dashboard
            dashboard_items = [{"id": "dashboard-root", "title": "Dashboard", "path": ""}]
            if role_id in [1, 2, 5]:
                dashboard_items.append({"id": "worklog-root", "title": "Work Log", "path": "/worklog"})
                
            menu_items.append({
                "partition": None,
                "items": dashboard_items
            })
    
            if projects_items:
                menu_items.append({
                    "partition": "Projects",
                    "items": projects_items
                })

            if reports_items:
                menu_items.append({
                    "partition": "Reports",
                    "items": reports_items
                })
                
            if settings_items:
                menu_items.append({
                    "partition": "Settings",
                    "items": settings_items
                })
            
            return menu_items
