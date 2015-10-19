from setuptools import setup


setup(
    name='twitterprobe',
    author='meejah',
    author_email='meejah@meejah.ca',
    url='https://meejah.ca/blog/twitter-probe',
    license='MIT',
    version='0.0.0',
    description='Inspect public Twitter timelines via Tor exits.',
    long_description='''
Downloads a public Twitter feed (like https://twitter.com/meejah) from
several different Tor exits and inspects the timeline for missing
tweets. Uses a Firefox user-agent header.

Contributions highly encouraged/welcome!
    ''',
    keywords=['python', 'twisted', 'tor'],
    install_requires=[
        'txtorcon>=0.14.0',
        'click>=5.1',
    ],
    entry_points={
        'console_scripts': [
            'twitterprobe = probe:cli'
        ]
    },
    classifiers=[
        'Framework :: Twisted',
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Operating System :: Unix',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Internet :: Proxy Servers',
        'Topic :: Internet',
        'Topic :: Security',
    ],
)
