from flask import Blueprint, render_template

main = Blueprint('main', __name__)


@main.route('/')
def home():
    return render_template('index.html')


@main.route('/about')
def about():
    return render_template('about.html')


@main.route('/contact')
def contact():
    return render_template('contacts.html')

@main.route('/products')
def products():
    return render_template('products.html')

@main.route('/services')
def services():
    return render_template('services.html')
