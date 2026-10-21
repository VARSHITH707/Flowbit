# Spoken list tests (Windows TTS, 16 kHz mono) -> data\list_*.wav, the words said in data\list_*.txt
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$clips = [ordered]@{
  "list_menu"   = "First, biryani. Second, dosa. Third, egg roti. And fifth, buttermilk."
  "list_nocomma" = "first biryani second dosa third egg roti and fifth buttermilk"
}
$root = Split-Path -Parent $PSScriptRoot
foreach ($k in $clips.Keys) {
  $s.SetOutputToWaveFile((Join-Path $root "data\$k.wav"), $fmt)
  $s.Speak($clips[$k]); $s.SetOutputToNull()
  Set-Content -Path (Join-Path $root "data\$k.txt") -Value $clips[$k] -Encoding UTF8
}
Write-Host "made list clips"
