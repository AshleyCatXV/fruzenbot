from aiogram.fsm.state import State, StatesGroup

class Form(StatesGroup):
    edit_nick_bot = State()
    
    admin_add_faction = State()
    admin_add_wl = State()
    admin_add_link = State()
    admin_rules_url = State()
    admin_adminchat_url = State()
    admin_flag_example = State()
    admin_set_global = State()
    admin_upload_map = State()
    admin_upload_rp = State()
    admin_rp_instruction = State()
    admin_edit_user = State()
    admin_send_to_user = State()
    admin_broadcast_text = State()
    admin_add_user_manually = State()

    # Интро
    intro_nick = State()
    intro_name = State()
    intro_faction_join = State()
    intro_faction_create_name = State()
    intro_faction_create_flag = State()

    # Формы
    form_text = State()
