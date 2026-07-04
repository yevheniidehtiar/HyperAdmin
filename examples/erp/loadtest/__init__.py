"""Locust load-testing suite for the ERP example.

The ``endpoints`` module is deliberately free of any ``locust`` import so its URL/weight/payload
logic can be unit-tested without the load-test extra installed. The ``auth_mixin`` and
``locustfile`` modules compose those helpers into Locust ``User`` classes.
"""
