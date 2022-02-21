---
title: Faraday Net::HTTP adapter v2.0.0.alpha-2以降で、Content-Typeに応じた文字コードがセットされるようになった
tags: Faraday Ruby Sinatra 文字コード encoding
author: kyntk
slide: false
---

[Qiita株式会社 Advent Calendar 2021](https://qiita.com/advent-calendar/2021/qiita)の14日目の担当は、Qiita株式会社CX向上グループの@kyntkです！

https://qiita.com/advent-calendar/2021/qiita

## はじめに

タイトルにある変更が対応されたPull Requestはこちらです。

https://github.com/lostisland/faraday-net_http/pull/13

## 前提

Faradayに2012年に以下のissueが作成されているように、FaradayでContent-Typeが`text/html; charset=utf-8`のようなレスポンスが返ってきても、`response.body`の文字コードは`ASCII-8BIT`になっています。

https://github.com/lostisland/faraday/issues/139

そのため、`response.body.encoding`では実際のbodyの文字コードがわからないので、特定の文字コードに変換したいときには初めにbodyの文字コードを判定しないと`Encoding::UndefinedConversionError`が発生する可能性がありました。

Qiitaでは記事内に[リンクカード](https://qiita.com/Qiita/items/c686397e4a0f4f11683d#%E3%83%AA%E3%83%B3%E3%82%AF%E3%82%AB%E3%83%BC%E3%83%89)を埋め込む際に、リンク先のタイトル等の情報をHTMLから取得していたのですが、一部文字化けを発生させてしまっていました。

## 結論

* Faraday Net::HTTP adapter v2.0.0.alpha-2 以降ではContent-Typeに応じた文字コードがセットされるようになった (現状まだアルファリリース)
* HTMLのcharsetに文字コードが設定されていても、Content-Typeに記されていない場合は`ASCII-8BIT`と判定されてしまうので、厳密にチェックが必要な場合は別途文字コードを確認してforce_encodingする必要がある

## 検証

ここからは動作の検証をしていきますが、文字コードなどについての補足情報を後半に乗せていますので、そちらもご覧ください。

### 事前準備

複数の文字コードで検証したいので、簡易的にSinatraでサーバーを立ててHTMLを返すようにします。
実際のコードは以下のリポジトリにおいてあります。

https://github.com/kyntk/faraday2-test

検証では、以下の3パターンを用意しました 

1. HTMLのcharset="utf-8"で、Content-Typeに"utf-8"が含まれている
1. HTMLのcharset="shift-jis"で、Content-Typeに"shift-jis"が含まれている
1. HTMLのcharset="shift-jis"で、Content-Typeに"shift-jis"が含まれていない

```ruby:app.rb
get '/utf8' do
  slim :utf8
end

get '/shift-jis' do
  headers \
    "Content-Type" => 'text/html;charset=shift_jis'
  slim :shift_jis
end

get '/shift-jis-no-charset' do
  headers \
    "Content-Type" => 'text/html'
  slim :shift_jis_no_charset
end
```

### Faradayの設定

実装したコードはこちらです。

```rb
require 'faraday'
require 'faraday/net_http'

Faraday.default_adapter = :net_http
conn = Faraday.new(url: 'http://localhost:4567') do |f|
  f.response(:logger)
end

response = conn.get('/utf8')
```

注意点としては、Faraday 2.0から、アダプターが本体から切り離されて、別途gem installの必要があることです。
また、v1では `default_adapter`が`:net_http`でしたが、`:test`に変わっています。 (以下のUPGRADING.mdはv2.0.0.alpha-3のものを参照)

https://github.com/lostisland/faraday/blob/v2.0.0.alpha-3/UPGRADING.md

そのため、Gemfileに、`faraday-net_http`を記載してインストールをすることが必要で、

```diff_ruby
gem 'faraday', '2.0.0.alpha-3'
+ gem 'faraday-net_http', '2.0.0.alpha-2'
```

さらにFaradayでリクエストをする前に以下のように`default_adapter`の記述が必要になります。

```diff_ruby
require 'faraday'
+ require 'faraday/net_http'

+ Faraday.default_adapter = :net_http
conn = Faraday.new(url: 'http://localhost:4567') do |f|
```

Faraday 2へのアップデートに伴う変更はこちらで別途まとめましたので、こちらもご覧ください。

https://qiita.com/kyntk/items/2a27172c0fc74939f628

### 動作検証

上記で作成した3つのエンドポイントに対してリクエストを行い、response.bodyの文字コードをUTF-8に変換します。

```ruby
response = conn.get('/shift-jis')
puts response.body.encoding
puts response.body.encode('UTF-8')
```

https://github.com/kyntk/faraday2-test/blob/main/faraday_test.rb

#### version1の場合

3パターンとも、`response.body.encoding`が`ASCII-8BIT`となっているため、encodeの処理で`Encoding::UndefinedConversionError`が発生してしまいました。

ログは一部加工、抜粋しています。

```
[DEBUG] request /utf8
I, [2021-12-06T08:04:12.927085 #46311]  INFO -- request: GET http://localhost:4567/utf8
I, [2021-12-06T08:04:12.952143 #46311]  INFO -- response: content-type: "text/html;charset=utf-8"
[DEBUG] response.body.encoding, ASCII-8BIT
faraday_test.rb:12:in `encode': "\\xE6" from ASCII-8BIT to UTF-8 (Encoding::UndefinedConversionError)
        from faraday_test.rb:12:in `<main>'
```

```
[DEBUG] request /shift-jis
I, [2021-12-06T08:04:55.299555 #46671]  INFO -- request: GET http://localhost:4567/shift-jis
I, [2021-12-06T08:04:55.330637 #46671]  INFO -- response: content-type: "text/html;charset=shift_jis"
[DEBUG] response.body.encoding, ASCII-8BIT
faraday_test.rb:17:in `encode': "\\x95" from ASCII-8BIT to UTF-8 (Encoding::UndefinedConversionError)
        from faraday_test.rb:17:in `<main>'
```

```
[DEBUG] request /shift-jis-no-charaset
I, [2021-12-06T08:05:44.666735 #47028]  INFO -- request: GET http://localhost:4567/shift-jis-no-charaset
I, [2021-12-06T08:05:44.690953 #47028]  INFO -- response: content-type: "text/html"
[DEBUG] response.body.encoding, ASCII-8BIT
faraday_test.rb:22:in `encode': "\\x95" from ASCII-8BIT to UTF-8 (Encoding::UndefinedConversionError)
        from faraday_test.rb:22:in `<main>'
```

### version2の場合

faradayとfaraday-net_httpのバージョンを2にupdateして検証します。
すると、Content-Typeが設定されているときは適切にbodyの文字コードが設定されているため、encodeにも成功しています。

```
[DEBUG] request /utf8
I, [2021-12-06T08:07:58.076577 #47801]  INFO -- request: GET http://localhost:4567/utf8
I, [2021-12-06T08:07:58.105417 #47801]  INFO -- response: content-type: "text/html;charset=utf-8"
[DEBUG] response.body.encoding, UTF-8
[DEBUG] response.body
<!DOCTYPE html><html lang="ja"><head><title>charaset utf-8</title><meta charset="utf-8" /></head><body><p>文字コードは UTF-8 です ☺</p></body></html>
```

```
[DEBUG] request /shift-jis
I, [2021-12-06T08:07:58.106100 #47801]  INFO -- request: GET http://localhost:4567/shift-jis
I, [2021-12-06T08:07:58.113733 #47801]  INFO -- response: content-type: "text/html;charset=shift_jis"
[DEBUG] response.body.encoding, Shift_JIS
[DEBUG] response.body
<!DOCTYPE html><html lang="ja"><head><title>charaset Shift_JIS</title><meta charset="shift-jis" /></head><body><p>文字コードは Shift_JIS です </p></body></html>
```

ただし、設定されていない場合は依然として`Encoding::UndefinedConversionError`が発生してしまいました。
そのため、レスポンスヘッダーのContent-Typeに文字コードが設定されていなくても厳密にHTMLの文字コードを判定したい場合は、body内に含まれるcharsetの記述を参照して、force_encodingをする必要があります。

```
[DEBUG] request /shift-jis-no-charset
I, [2021-12-06T08:07:58.114818 #47801]  INFO -- request: GET http://localhost:4567/shift-jis-no-charset
I, [2021-12-06T08:07:58.120169 #47801]  INFO -- response: content-type: "text/html"
[DEBUG] response.body.encoding, ASCII-8BIT
faraday_test.rb:22:in `encode': "\\x95" from ASCII-8BIT to UTF-8 (Encoding::UndefinedConversionError)
        from faraday_test.rb:22:in `<main>'
```


## 改めて、結論

* Faraday Net::HTTP adapter v2.0.0.alpha-2 以降ではContent-Typeに応じた文字コードがセットされるようになった (現状まだアルファリリース)
* HTMLのcharsetに文字コードが設定されていても、Content-Typeに記されていない場合は`ASCII-8BIT`と判定されてしまうので、厳密にチェックが必要な場合は別途文字コードを確認してforce_encodingする必要がある

## 補足

検証は以上となりますが、調査をしていく中で文字コードについての背景知識が必要だったので、自分の整理も含めてまとめます。
基本的にはこちらの本を読んだのですが、やはり本を読んで体系的に学ぶのが一番いいと思いました。

https://www.amazon.co.jp/%EF%BC%BB%E6%94%B9%E8%A8%82%E6%96%B0%E7%89%88%EF%BC%BD%E3%83%97%E3%83%AD%E3%82%B0%E3%83%A9%E3%83%9E%E3%81%AE%E3%81%9F%E3%82%81%E3%81%AE%E6%96%87%E5%AD%97%E3%82%B3%E3%83%BC%E3%83%89%E6%8A%80%E8%A1%93%E5%85%A5%E9%96%80-WEB-DB-PRESS-plus-ebook/dp/B07M98R3S5


### 文字コードとは

文字を扱うとき、コンピュータはその文字に振られた番号(バイト表現)を処理していますが、この番号や、番号と文字との対応関係のことを文字コードといいます。
このように文字を、対応する番号である文字コードで表現することを符号化といいます。
そして、表現したい文字列の集まりを文字集合といい、その文字の集合に符号を振ったものを符号化文字集合といいます。

単語が多いですが、「[ASCII 文字コード表](https://www.google.com/search?q=ASCII+%E6%96%87%E5%AD%97%E3%82%B3%E3%83%BC%E3%83%89%E8%A1%A8&sxsrf=AOaemvJLX3JKx19wYLFylKhwHdEWAbXvkg:1639090379313&source=lnms&tbm=isch&sa=X&ved=2ahUKEwiN5r6-59f0AhVOxGEKHf0fBewQ_AUoAXoECBgQAw&cshid=1639090493884041&biw=2210&bih=1134&dpr=0.85) 」などでググってもらえば符号化文字集合のイメージがつくと思います。

UTF-8やShift_JIS、EUC-JPといったものも文字集合の一種です。
ただし、同じ文字であっても文字集合が異なれば符号が異なることがあるので、これを変換する必要があります。
たとえば以下のように、「あ」という文字の符号はUTF-8、Shift_JIS、EUC-JPで異なっています。

```ruby
# UTF-8
irb> 'あ'.encode('UTF-8').bytes.map { _1.to_s(16).upcase }
=> ["E3", "81", "82"]
# Shift_JIS
irb> 'あ'.encode('Shift_JIS').bytes.map { _1.to_s(16).upcase }
=> ["82", "A0"]
# EUC-JP
irb> 'あ'.encode('EUC-JP').bytes.map { _1.to_s(16).upcase }
=> ["A4", "A2"]

# 同じものもある
irb> 'a'.encode('UTF-8').bytes.map { _1.to_s(16).upcase }
=> ["61"]
irb> 'a'.encode('Shift_JIS').bytes.map { _1.to_s(16).upcase }
=> ["61"]
irb> 'a'.encode('EUC-JP').bytes.map { _1.to_s(16).upcase }
=> ["61"]
```

これによって、ある符号を異なった文字コードとして解釈してしまうといわゆる文字化けが起きます。
たとえば、Shift_JISで「文字コード」と書かれた文字をUTF-8と解釈してブラウザで表示をしてみると、
![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/143317/ab63364b-499d-801a-a03a-0d400f8f9011.png)
このように読めない文字になってしまいました。

### 外部コードと内部コード

プログラムの中では、外部から入力された文字列を処理することもありますが、この際に入力する文字コードとプログラム内部で使っている文字コードが異なると、これも文字化けを引き起こす要因になります。そのため、外部からの入力の際に、内部で扱っている文字コードへの変換が必要となります。また逆に内部から外部への出力の際にも変換を行う必要があります。

### Code Set Independent (CSI) 方式

内部コードは多くのプログラミング言語は1つの文字コードで処理することが多いのですが(UCS方式)、Rubyでは先程の例のように1つのアプリケーション内で複数の文字コードを使えるようになっています。これをCSI方式といいます。Rubyでは文字列ごとに文字コードの情報を持っています。

RubyがなぜCSI方式を採用したのかはこちらが詳しいです。

https://jp.quora.com/Ruby-deha-naze-UCS-seiki-ka-wo-saiyou-shi-tei-nai-node-shou-ka

### Content-Type

Content-TypeはHTTPレスポンスヘッダーの一つで、リソースのメディア種別を示しますが、ここで`charset`を使用して文字コードを示すことができます。今回の例ではHTMLを取得したときにその文字コードを判定するために参照しています。

https://developer.mozilla.org/ja/docs/Web/HTTP/Headers/Content-Type

### ASCII-8bit

もう一つ補足しておきたいのはFaradayのレスポンスでデフォルトで設定されている`ASCII-8bit`についてです。

https://ruby-doc.org/core-3.0.3/Encoding.html 

によると、以下のように書かれています。

> Encoding::ASCII_8BIT is a special encoding that is usually used for a byte string, not a character string. But as the name insists, its characters in the range of ASCII are considered as ASCII characters. This is useful when you use ASCII-8BIT characters with other ASCII compatible characters.

DeepL翻訳

> Encoding::ASCII_8BIT は特殊なエンコーディングで、通常は文字列ではなくバイト文字列に使用されます。しかし、その名が示すように、ASCIIの範囲内にあるその文字はASCII文字とみなされます。これは、ASCII-8BITの文字を他のASCII互換の文字と一緒に使うときに便利です。

という`ASCII-8bit`は特殊な文字コードのようです。


## 参考

もっと詳しく知りたい人は、それぞれの文字集合の違いや、文字化けについてなど詳しく說明されているので、ぜひこちらの本を読んでみてください。

https://www.amazon.co.jp/%EF%BC%BB%E6%94%B9%E8%A8%82%E6%96%B0%E7%89%88%EF%BC%BD%E3%83%97%E3%83%AD%E3%82%B0%E3%83%A9%E3%83%9E%E3%81%AE%E3%81%9F%E3%82%81%E3%81%AE%E6%96%87%E5%AD%97%E3%82%B3%E3%83%BC%E3%83%89%E6%8A%80%E8%A1%93%E5%85%A5%E9%96%80-WEB-DB-PRESS-plus-ebook/dp/B07M98R3S5

## 終わりに

明日の[Qiita株式会社 Advent Calendar 2021](https://qiita.com/advent-calendar/2021/qiita)は、@WakameSun が担当しますのでお楽しみに！

