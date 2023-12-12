# -*- coding: utf-8 -*-
{
    'name': "Zerynth Platform App",
    'summary': """
        Zerynth Platform App
    """,
    'description': """
        Zerynth Platform App, connect your devices
    """,
    'author': "Zerynth",
    'website': "https://it.zerynth.com/",
    'category': 'Services',
    'version': '14.3',
    "license": "LGPL-3",
    'price': 150,
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
        "views/zcloud_log.xml",
        "views/zcloud_data.xml",
        "views/product.xml",
        "views/routing_workcenter.xml",
        "views/production.xml",
        "views/part_program_variable.xml",
        "views/productivity_loss.xml",
        "wizard/confirm_start_workorder_wizard_views.xml",
    ],
    'application': True
}
