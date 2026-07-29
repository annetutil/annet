def _map_device_result(device: Device, gen_res: GenerationResult, gdiffs: list[ShowGenDiff]) -> DeviceResult:
    str_diff = render_diff(gdiffs)
    str_gen_err = render_generation_errors([gen_res])

    diff_gens = set()
    error_gens = set()
    for gen_data in gen_res.data:
        if gen_data.error:
            error_gens.add(gen_data.name)
    for gen_diff in gdiffs:
        if gen_diff.error:
            error_gens.add(gen_diff.name)
        elif has_diff(gen_diff.diff.splitlines()) and gen_diff.name not in error_gens:
            diff_gens.add(gen_diff.name)

    return DeviceResult(
        ann_commit="xx",
        cfg_commit="xx",
        ann_gen_commit="xxxx",
        device=device,
        status=self._get_device_res_status(gdiffs, str_diff, str_gen_err),
        message=f"{str_diff}\n\n{str_gen_err}".strip(),
        error_generators=list(error_gens),
        diff_generators=list(diff_gens),
    )
