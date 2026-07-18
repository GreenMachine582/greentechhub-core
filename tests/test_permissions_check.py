from greentechhub_core.permissions import Permission, Role, has_permission

# has_permission — containment


def test_has_permission_true_when_permission_is_granted():
    perm = Permission("portfolio.view")
    assert has_permission(object(), perm, granted={perm}) is True


def test_has_permission_false_when_permission_is_not_granted():
    perm = Permission("portfolio.view")
    other = Permission("portfolio.edit")
    assert has_permission(object(), perm, granted={other}) is False


def test_has_permission_false_for_empty_granted():
    perm = Permission("portfolio.view")
    assert has_permission(object(), perm, granted=frozenset()) is False


def test_has_permission_works_with_frozenset():
    perm = Permission("portfolio.view")
    assert has_permission(object(), perm, granted=frozenset({perm})) is True


def test_has_permission_works_with_a_plain_set():
    perm = Permission("portfolio.view")
    assert has_permission(object(), perm, granted={perm}) is True


# has_permission — identity is pass-through only


def test_has_permission_ignores_identity_shape():
    perm = Permission("portfolio.view")
    # identity is never inspected -- any object, including a plain sentinel
    # with no Identity-shaped attributes at all, works identically.
    assert has_permission("not-an-identity", perm, granted={perm}) is True
    assert has_permission(None, perm, granted={perm}) is True


# has_permission — composing granted from a Role


def test_has_permission_true_for_a_permission_in_a_role_bundle():
    role = Role(
        name="Trader",
        permissions={Permission("portfolio.view"), Permission("portfolio.edit")},
    )
    granted = role.permissions | {Permission("reports.view")}
    assert has_permission(object(), Permission("reports.view"), granted=granted) is True
    assert has_permission(object(), Permission("import.run"), granted=granted) is False
