import formencode

class ConnForm(formencode.Schema):
    allow_extra_fields = True
    filter_extra_fields = True
    server = formencode.validators.String(not_empty=True)
    nickname = formencode.validators.String(not_empty=True)
    channel = formencode.validators.String(not_empty=True)
    

