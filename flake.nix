{
  outputs = {
    self,
    nixpkgs,
    flake-utils,
  }:
    flake-utils.lib.eachDefaultSystem
    (
      system: let
        pkgs = import nixpkgs {
          inherit system;
        };

        python = pkgs.python314;

        pythonPkgs = python.withPackages (ps: with ps; [
          pip
          django
          ical
        ]);
      in rec {
        devShells.default = pkgs.mkShell {
          packages = [
            pythonPkgs
          ];
        };
      }
    );
}


