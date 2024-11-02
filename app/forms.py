from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    user_type = SelectField('Login as', choices=[('customer', 'Customer'), ('staff', 'Staff')], validators=[DataRequired()])
    submit = SubmitField('Login')