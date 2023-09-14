{
  description = "Flake for developing on Wenjim";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {

        devShell = pkgs.mkShell {
          buildInputs = with pkgs; [
            stdenv.cc.cc.lib
            python311
            poetry
          ];
          shellHook = ''
            export LD_LIBRARY_PATH=${pkgs.stdenv.cc.cc.lib}/lib/
          '';
        };
      }
    );
}
