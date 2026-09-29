# Standard profile examples

The portal exposes three fictional project trace chains from
`engineering_gateway.api.example_projects`. Their graphs are checked against
the executable `arp4754a@2.0` and `do-178c@2.0` profiles in CI. The example
elements are not native external records, test results, or approved baselines.

The intended composition for the first vertical slices is:

```yaml
project:
  standards:
    system_development: ARP4754A
    software: DO-178C
    safety: ARP4761
```

Profiles define element types, typed relations, lifecycle states, mandatory artifacts, traceability obligations and deterministic validation rules. They must be composable and independently versioned.
