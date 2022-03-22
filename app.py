from flask import render_template
import connexion
import logging


# Create the application instance
app = connexion.FlaskApp(__name__,port=8888,specification_dir='./')
# Read the swagger.yml file to configure the endpoints
app.add_api('swagger.yml')
# Routes the homepae
@app.route('/')
def home():
    """
    creates the view for the homepage
    """
    return render_template('home.html')

if __name__ == '__main__':
    # Creates a logger file to see the different logs from the API
    logging.basicConfig(
        filename="wrapper.log",
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S')
    # Runs API
    app.run(host='0.0.0.0', port=8888)
