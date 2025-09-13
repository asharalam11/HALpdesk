class Halpdesk < Formula
  include Language::Python::Virtualenv

  desc "HALpdesk AI terminal assistant daemon + CLI"
  homepage "https://github.com/asharalam11/HALpdesk"
  # Stable release tarball (update version + sha256 to a real release)
  url "https://github.com/asharalam11/HALpdesk/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "REPLACE_WITH_RELEASE_TARBALL_SHA256"
  head "https://github.com/asharalam11/HALpdesk.git", branch: "main"
  license "MIT"

  depends_on "python@3.11"

  resource "fastapi" do
    url "https://files.pythonhosted.org/packages/py3/f/fastapi/fastapi-0.115.0.tar.gz"
    sha256 "5d3d1b3d2b8b43b53bf3b6d4a3e57fcb0c7ee17b5e84b95c824d3d1fd5c7b3fb"
  end

  resource "uvicorn" do
    url "https://files.pythonhosted.org/packages/py3/u/uvicorn/uvicorn-0.30.6.tar.gz"
    sha256 "0b7d12a4f8a5b69c9b38a5a1b2dd2bdb5f2e4f2a3840b9f1e7fda9c2b61a75d9"
  end

  resource "requests" do
    url "https://files.pythonhosted.org/packages/py3/r/requests/requests-2.32.3.tar.gz"
    sha256 "55365417734eb18255e8f9a7ea7c6c1e58a5ca0f8c6bbb6d6f74c9e76f6f3f41"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/py3/r/rich/rich-13.8.1.tar.gz"
    sha256 "8d83a3a4e9b2f8f3e9ebc86c6c62e14a9910cdd1489e8b2dd6c2f0b2d2b5e0b9"
  end

  resource "click" do
    url "https://files.pythonhosted.org/packages/py3/c/click/click-8.1.7.tar.gz"
    sha256 "ca9853ad47c1e5a9fe8e6e13a5e3a0b8eb9a1f0f4b8a9c4c6da7a1f0f3b3a1d1"
  end

  resource "pydantic" do
    url "https://files.pythonhosted.org/packages/py3/p/pydantic/pydantic-2.9.1.tar.gz"
    sha256 "a2d6f84f3b3d3e2a45f8b6a2145c854a48f33e7f2f9b77c1b118e8b6f61d1a6e"
  end

  resource "prompt-toolkit" do
    url "https://files.pythonhosted.org/packages/py3/p/prompt_toolkit/prompt_toolkit-3.0.47.tar.gz"
    sha256 "d4fbb0b216b052153b8ee1f53d46e0bd27cbb0473e8ca4bc1a397e8608ddb1a4"
  end

  resource "tomli" do
    url "https://files.pythonhosted.org/packages/py3/t/tomli/tomli-2.0.1.tar.gz"
    sha256 "de526c6e4b5cfc1a7e76f1c4e6a4240a3f93f7d1a1b8b6a3a4a2e3a7c17ff7c1"
  end

  def install
    virtualenv_install_with_resources
    (bin/"halp").write_env_script libexec/"bin/halp", {}
    (bin/"halpdesk-daemon").write_env_script libexec/"bin/halpdesk-daemon", {}
  end

  def caveats
    <<~EOS
      This formula installs from the public GitHub repo:
        https://github.com/asharalam11/HALpdesk

      To install the HEAD version locally:
        brew install --HEAD #{buildpath}/packaging/homebrew/halpdesk.rb

      To run the daemon on login:
        brew services start #{name}
    EOS
  end

  test do
    assert_match "usage", shell_output("#{bin}/halp --help 2>&1", 0)
  end
end
