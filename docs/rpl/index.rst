Routing policy list (RPL)
===================================

With ``annet`` you can set routing policies in vendor-agnostic way. It consists of 2 parts:
RouteMap handlers and policy generators.

Configuring policies
***************************

Each policy is represented by a single function registered in ``RouteMap`` instance, while each statement is produced using context manager.

Quickstart
---------------------------

1. Create a ``RouteMap``. Use Device type according to your storage to parametrize it.

.. code-block:: python

   from annet.rpl import RouteMap
   from annet.adapters.netbox.common.models import NetboxDevice  # replace with your type

   routemap = RouteMap[NetboxDevice]()

2. Create a handler and attach it to routemap. It will receive two arguments: device (according to your storage) and route instance.

.. code-block:: python

    from annet.rpl import Route
    @routemap
    def rule_example(device: NetboxDevice, route: Route):
        ...

3. Enter context manager to start building new rule. Use ``R``-object to specify how the rule will checked.
    Arguments ``number`` and ``name`` are used to order statements on some vendors.

.. code-block:: python

    from annet.rpl import R


    @routemap
    def rule_example(device: NetboxDevice, route: Route):
        with route(R.as_path_length >= 1, number=4, name="n4") as rule:
            ...

4. Modify route attributes:

.. code-block:: python

    @routemap
    def rule_example(device: NetboxDevice, route: Route):
        with route(R.as_path_length >= 1, number=4, name="n4") as rule:
            rule.set_metric(100)  # modify metric for the route

5. Set action:

.. code-block:: python

    @routemap
    def rule_example(device: NetboxDevice, route: Route):
        with route(R.as_path_length >= 1, number=4, name="n4") as rule:
            rule.set_metric(100)
            rule.allow()  # allow matched route


Matching routes
------------------------

You can match route attributes against calculated values or named entities. Conditions are built using ``R`` variable and passed when entering route context.
Different attributes support different operations, some can be matched for equality, some have <= comparison, for others it is checked if they have specific values.

You can pass multiple conditions or combine them using ``&`` sign, the result is the same. Normally, you cannot have multiple conditions on the same field
(only ``<=`` together with ``>=`` are combined into ``BETWEEN_INCLUDED``).

As-path filters, ip prefix lists and communities are referenced by their name.

Here are some examples:

.. code-block:: python

    R.as_path_length >= 1
    R.as_path_length >= 1 & R.as_path_length <= 10
    R.protocol == "bgp"
    R.as_path_filter("AS_PATH_FILTER_NAME")
    R.community.has("COMMUNITY_FILTER_NAME", "COMMUNITY_FILTER_NAME2")
    R.match_v6("IPV6_PREFIX_LIST_NAME", or_longer=(29, 48))



Additionally, you can specify conditions outside of handler function and reuse them:

.. code-block:: python

    CONDITION = R.as_path_length >= 1 & R.protocol == "bgp"

    @routemap
    def rule_example(device: NetboxDevice, route: Route):
        with route(CONDITION, number=4, name="n4") as rule:
            ...

Custom conditions can be added to an expression, but builtin generators won't be able to process them without customizations.

.. code-block:: python

    from annet.rpl import SingleCondition, ConditionOperator


    @routemap
    def rule_example(device: NetboxDevice, route: Route):
        condition = SingleCondition(
            field="some_custom_field_name",
            operator=ConditionOperator.EQ,
            value="some value",
        )
        with route(condition, number=4, name="n4") as rule:
            ...


Route actions
------------------------

To apply route attribute changes you can call various methods on the objected retrieved from route context manager.
Here are some examples:

.. code-block:: python

    @routemap
    def rule_example(device: NetboxDevice, route: Route):
        with route(CONDITION, number=4, name="n4") as rule:
            rule.set_local_pref(100)
            rule.set_metric(100)
            rule.add_metric(200)
            rule.community.set("COMMUNITY_NAME_EXAMPLE")
            rule.community.add("COMMUNITY_NAME_EXAMPLE")
            rule.community.remove("COMMUNITY_NAME_EXAMPLE")
            rule.as_path.set(12345, "123456")

Additionally, you can add custom actions, but you will need to customize generator to support them:

.. code-block:: python

    from annet.rpl import ActionType, SingleAction

    @routemap
    def rule_example(device: NetboxDevice, route: Route):
        with route(CONDITION, number=4, name="n4") as rule:
            rule.custom_action(SingleAction(
                field="some_custom_field_name",
                type=ActionType.CUSTOM,
                value="some value",
            ))


Creating entities
*******************************

There are several entities that should be created separately:

* Prefix lists
* Communities
* AS-Path filters

Running generator
*************************

Currently there is only en example of policy generator, but it will be improved soon.

