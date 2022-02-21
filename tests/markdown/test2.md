fp-tsでは `pipe` という関数で関数を繋げていきます。Haskellの `do` やScalaの `for` に相当するものですが、
表現力はなかり見劣りします。

## Monadクラスを使用した場合の関数の２形態

Monadクラスの例として`Option`を用いていますが、`Reader`でも`TaskEither`でも共通の話題です。

Monadクラスで関数を扱っていると、以下のような関数の形態に出くわします。形態ごとに関数の繋げ方が違ってきます。


### liftされた関数

liftされた関数はちゃんとした関数なので他の関数と合成が可能。

```typescript
(ma: Option<A>) => Option<B> // liftされた関数
```

### 閉じ込められた関数

Monadクラスのインスタンスの中に関数が閉じ込められているので、これ自体は関数ではない。なので、他の関数との合成はできないし、そのままでは呼び出せない。その代わり閉じ込められた関数を呼び出す仕組みが用意されている。

```typescript
Option<(a: A) => B> // 閉じ込められた関数
```

## 関数を繋げる: liftされた関数用

以下の方法で関数をliftします。共通で代表的なものは以下の２つです。他にも亜種、各Monadクラス特有のliftについて色々あります。

### map

`(a: A) = >B`という関数を`(ma: Option<A>) => Option<B>`に変換する。

```typescript
map: <A, B>(f: (a: A) => B) => (ma: Option<A>) => Option<B>
```

### chain

`(a: A) => Option<B>`という型の関数を`(ma: Option<A>) => Option<B>`に変換する。

```typescript
chain: <A, B>(f: (a: A) => Option<B>) => (ma: Option<A>) => Option<B>
```

## 関数を繋げる: 閉じ込められた関数用

### ap

`ap` を使うことで閉じ込められた関数 `<B>(mab: Option<(a: A) => B>)` を
引数 `<A>(ma: Option<A>)` で呼び出すことができます。これにも色々亜種、各Monadクラス特有のものがあります。

```typescript
ap: <A>(ma: Option<A>) => <B>(mab: Option<(a: A) => B>) => Option<B>) => Option<B>
```
