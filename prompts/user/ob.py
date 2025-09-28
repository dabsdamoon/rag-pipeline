OB_USER_PROMPT = """
The user asking question is a member of family who's preparing to give birth and thus interested in learning about obstetrics.
The user is looking for information about pregnancy, childbirth, and postpartum care.
- username: {username}
- age: {age}
- address: {address}
- is pregnant: {is_pregnant}
- estimated delivery date: {estimated_delivery_date}
- number of children: {number_of_children}
- insurance provider: {insurance_provider}
"""