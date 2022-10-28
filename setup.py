from setuptools import setup

setup(
    name='geehotspot',
    version='0.6.0',
    description='GEE HotSpot Trend creation package',
    url='https://github.com/initze/GEE_HotSpot',
    author='Ingmar Nitze',
    author_email='ingmar.nitze@awi.de',
    license='BSD 2-clause',
    packages=['geehotspot'],
    install_requires=['earthengine-api'
                      ],

    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3'
    ],
)
