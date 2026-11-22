{
  description = "Configuration generation and deployment for network equipment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = {
    self,
    nixpkgs,
  }: {
    overlays.default = final: prev: {
      pythonPackagesExtensions =
        prev.pythonPackagesExtensions
        ++ [
          (python: _: let
            # These dependencies are not packaged in Nixpkgs.
            buildPypi = {
              pname,
              version,
              hash,
              wheel ? false,
              dependencies ? [],
              optional-dependencies ? {},
            }:
              python.buildPythonPackage {
                pname = pname;
                version = version;
                format =
                  if wheel
                  then "wheel"
                  else "pyproject";
                build-system = final.lib.optional (!wheel) python.setuptools;
                dependencies = dependencies;
                optional-dependencies = optional-dependencies;
                src = final.fetchPypi ({
                    pname = pname;
                    version = version;
                    hash = hash;
                  }
                  // final.lib.optionalAttrs wheel {
                    format = "wheel";
                    python = "py3";
                    dist = "py3";
                  });
              };

            # Use release wheels for dependencies with pinned build backends.
            adaptix = buildPypi {
              pname = "adaptix";
              version = "3.0.0b12";
              hash = "sha256-gVbwVJuW/NGT0T78p7+9o5s9Y4kIVVbZMOIEwJ+a5u0=";
              wheel = true;
            };
            dataclass-rest = buildPypi {
              pname = "dataclass_rest";
              version = "0.5.0";
              hash = "sha256-gF149lUlBi1tJj1ZnJKlpTEjlAXBD6i7RlzK7th7YNs=";
              dependencies = [adaptix];
            };
            annetbox = buildPypi {
              pname = "annetbox";
              version = "1.1.2";
              hash = "sha256-J9xsVXBRoLMzc0x9iQbzlrbdbGmQPqqmk+Sag7+6l2U=";
              wheel = true;
              dependencies = [adaptix dataclass-rest python.python-dateutil];
              optional-dependencies = {
                "sync" = [python.requests];
              };
            };
            contextlog = buildPypi {
              pname = "contextlog";
              version = "1.1";
              hash = "sha256-pJNHNEeVXpSH1IKnNlYuxVq2KwAQWtX18hxqUlArGEE=";
              dependencies = [python.colorlog];
            };
            valkit = buildPypi {
              pname = "valkit";
              version = "0.1.4";
              hash = "sha256-NSH8wY4CQH7K3M8DE8geIxkH4hsOm6X/1HO49IgOdAk=";
            };
          in {
            annet = python.buildPythonPackage rec {
              pname = "annet";
              version = "0.0+${self.shortRev or "local"}";
              src = self;
              pyproject = true;
              build-system = [python.setuptools];
              env."VERSION" = version;

              dependencies = [
                # packaged in nixpkgs:
                python.colorama
                python.jsonpatch
                python.jsonpointer
                python.mako
                python.ordered-set
                python.packaging
                python.pygments
                python.pyyaml
                python.ruamel-yaml
                python.tabulate
                python.yarl

                # packaged by us:
                adaptix
                contextlog
                dataclass-rest
                valkit
              ];

              optional-dependencies = {
                "netbox" = [annetbox python.requests-cache] ++ annetbox.optional-dependencies.sync;
              };

              pythonImportsCheck = [
                "annet.annet"
                "annet.adapters.file.provider"
                "annet.adapters.netbox.provider"
              ];

              meta.mainProgram = "annet";
            };
          })
        ];
    };

    packages =
      nixpkgs.lib.genAttrs [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ] (system: let
        pkgs = import nixpkgs {
          system = system;
          overlays = [self.overlays.default];
        };
        python = pkgs.python3Packages;
        annet = python.toPythonApplication (python.annet.overridePythonAttrs (old: {
          dependencies = old.dependencies ++ builtins.concatLists (builtins.attrValues old.optional-dependencies);
          pythonImportsCheck = old.pythonImportsCheck ++ ["annet.adapters.netbox.v42.storage"];
        }));
      in {
        default = annet;
        annet = annet;
      });
  };
}
