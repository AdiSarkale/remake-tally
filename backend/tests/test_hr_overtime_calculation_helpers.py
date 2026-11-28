from app.modules.hr.overtime import round_minutes,scope_matches

def test_rounding_modes_are_policy_values():
 assert round_minutes(17,{"method":"none"})==17
 assert round_minutes(17,{"method":"floor","increment_minutes":15})==15
 assert round_minutes(17,{"method":"ceil","increment_minutes":15})==30
 assert round_minutes(22,{"method":"nearest","increment_minutes":15})==15
 assert round_minutes(23,{"method":"nearest","increment_minutes":15})==30

def test_policy_scope_matches_only_selected_dimensions():
 class E: employee_type="staff";department="Operations"
 class O: branch_id="b1";department="Operations"
 class R: shift_type_id="s1"
 assert scope_matches({"branch_ids":["b1"],"employee_types":["staff"]},E(),O(),R(),"scheduled_workday")
 assert not scope_matches({"branch_ids":["b2"]},E(),O(),R(),"scheduled_workday")
 assert scope_matches({},E(),O(),R(),"holiday")
