{ pkgs }: {
    deps = [
        pkgs.ffmpeg-full
        pkgs.python310Full
        pkgs.python310Packages.pip
    ];
}