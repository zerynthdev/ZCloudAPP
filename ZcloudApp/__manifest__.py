# -*- coding: utf-8 -*-
{
    'name': "Zerynth Cloud App",
    'summary': """
        Zerynth Cloud App
    """,
    'description': """
        Zerynth Cloud App, connect your devices
    """,
    'author': "Zerynth",
    'website': "https://it.zerynth.com/",
    'category': 'Services',
    'version': '14.1',
    "license": "LGPL-3",
    'price': 150,
    'support':'odoo@bloomup.it',
    "images": ['static/src/img/thumbnail.png'],
    'currency': 'EUR',
    'depends': [
        'base',
        'mrp'
    ],
    'data': [
        "data/groups.xml",
        "security/ir.model.access.csv",
        "security/rules.xml",
        "data/actions.xml",
        "data/crons.xml",
        "views/menu.xml",
        "views/zcloudqueue.xml",
        "views/zcloud_device.xml",
        "views/zcloud_device_line.xml",
        "views/zcloud_workspace.xml",
        "views/zcloud_fleet.xml",
        "views/workcenter.xml",
        "views/workorder.xml",
        "views/config.xml",
        "views/zcloud_log.xml"
    ],
    'application': True
}
