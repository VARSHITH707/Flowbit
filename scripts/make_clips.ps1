Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$short = "The quick brown fox jumps over the lazy dog. Please send the report to Maria by Friday afternoon."
$para = "Local speech recognition runs entirely on this laptop. The graphics card accelerates the model, and the text is inserted into the window that had focus when recording started. Custom vocabulary helps with names such as Kubernetes, PostgreSQL and PySide six. If recognition fails, the application reports an error instead of inventing text. "
$long = ($para * 14).Trim()
foreach ($c in @(@('short',$short),@('long',$long))) {
  $s.SetOutputToWaveFile("Z:\Wispr Flow\data\tts_$($c[0]).wav", $fmt)
  $s.Speak($c[1]); $s.SetOutputToNull()
  Set-Content -Path "Z:\Wispr Flow\data\tts_$($c[0]).txt" -Value $c[1] -Encoding utf8
}
