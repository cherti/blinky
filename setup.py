from distutils.core import setup

setup(
    name='blinky',
    version='0.19',
    author='Jonas Große Sundrup',
    author_email='cherti@letopolis.de',
    packages=['blinky'],
    scripts=['scripts/blinky', 'scripts/rebuild-blinky.sh'],
    install_requires=[
        #'pyalpm'  # not on pypi
		#'colordiff'  # not on pypi
        'requests',
        'termcolor'
    ],
    url='https://github.com/cherti/blinky',
    license='GPLv3',
    description='AUR-helper with minimal hassle',
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown"
)
