from annet.mesh.registry import MeshRulesRegistry, GlobalOptions

registry = MeshRulesRegistry()


@registry.device("{name:.*}")
def foo(global_opts: GlobalOptions):
    global_opts.local_as = 12345
