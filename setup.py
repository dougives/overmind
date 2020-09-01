from setuptools import setup

setup(
   name='overmind',
   version='0.0.0',
   description='SC2 Replay Data Miner',
   author='Doug Ives',
   author_email='github@dou.gives',
   packages=[ 'overmind' ],
   install_requires=[ 'sc2reader', 'python-dotenv' ],
)
