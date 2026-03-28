import os

path = r"c:\Users\Administrador\Desktop\Amigão_do_Meio_Ambiente\alembic\versions\e91d20acba9c_sprint_2_models.py"

with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if "op.drop_table('pagc_lex')" in line and i < 200:
        skip = True
    
    if skip and "op.add_column('audit_logs" in line and i < 200:
        skip = False
        
    if "op.create_table('secondary_unit_lookup" in line and i > 130:
        skip = True
    
    if skip and "op.drop_table('task_dependencies')" in line and i > 700:
        skip = False
        
    if not skip:
        new_lines.append(line)

with open(path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)
