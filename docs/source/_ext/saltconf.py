# -*- coding: utf-8 -*-

def setup(app):
    # Let's teach sphinx about Salt's conf_* roles
    app.add_crossref_type(directivename="conf_master", rolename="salt_conf_master",
            indextemplate="pair: %s; conf_master")
    app.add_crossref_type(directivename="conf_minion", rolename="salt_conf_minion",
            indextemplate="pair: %s; conf_minion")
    app.add_crossref_type(directivename="conf_cloud", rolename="salt_conf_cloud",
            indextemplate="pair: %s; conf_minion")
    app.add_crossref_type(directivename="conf_log", rolename="salt_conf_log",
            indextemplate="pair: %s; conf_logging")
