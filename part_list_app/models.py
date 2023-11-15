from django.db import models


class Part(models.Model):
    """
    Part モデルは、部品情報を保持します。

    フィールド説明:
    - code: 部品コード。
    - name: 部品名。
    """
    code = models.CharField('部品コード', max_length=3)
    name = models.CharField('部品名', max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = '部品'


class Composition(models.Model):
    """
    Composition モデルは、構成情報を保持します。

    フィールド説明:
    - parent_id: 親id。 製品の場合、parent == null。
    - sort: 並び順。
    - part: 部品。
    - quantity: 数。
    """
    # 以下の書き方をしてしまうと、親を消した場合、子も自動的に消されてしまい
    # undo、redo処理用の子の更新履歴情報を保持出来なくなってしまいます。
    # 末端から消す処理を作成すれば可能かと思うがそれは相当複雑になってしまうため、以下の書き方は中止しました。
    # parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    parent_id = models.IntegerField(verbose_name='親id', null=True, blank=True)
    # 外部キー制約を入れ可能な限りデータ不整合のない状態を保つ為修正を実施する事と致しました。
    # parent = models.ForeignKey(Part, verbose_name='親部品',
    #                           on_delete=models.CASCADE, null=True, blank=True)
    sort = models.IntegerField('並び順')
    part = models.ForeignKey(Part, verbose_name='部品',
                             related_name="part_compositions",
                             on_delete=models.CASCADE)
    quantity = models.IntegerField('数', null=True, default=None)

    def __str__(self):
        #    return f'Parent_id: {self.parent_id}, Part: {self.part}'
        return f'Parent: {self.parent}, Part: {self.part}'

    class Meta:
        verbose_name = '構成'


class CompositionChangeSet(models.Model):
    """
    CompositionChangeSet モデルは、一つのトランザクション内で１つインスタンスを発生させ
    複数のCompositionHistoryをまとめます。

    フィールド説明:
    - product: 変更が発生した Composition インスタンスの製品(parent == null)外部キー。
    - timestamp: 構成変更セットが作成された日時。
    """
    product = models.ForeignKey(Composition, on_delete=models.CASCADE, verbose_name='製品')
    timestamp = models.DateTimeField('変更日時', auto_now_add=True)

    def __str__(self):
        return f'CompositionChangeSet at {self.timestamp}'

    class Meta:
        verbose_name = '構成変更セット'
        db_table = "part_list_app_composition_change_set"


class CompositionHistory(models.Model):
    """
    CompositionHistory モデルは、Composition モデルの変更履歴を追跡します。

    フィールド説明:
    - composition_change_set: 一つのトランザクション内で発生した 更新されたComposition インスタンスの外部キー。
    - composition_original_id: 更新が発生した Composition インスタンスのキー。
        Compositionを削除した場合でも消えないようにする為、ForeignKeyはやめました。
        DjangoのORMは、外部キー関連のフィールドに対して_idというサフィックスを自動的に追加します。
        そのため、composition_idという名前は、もともと外部キーとして存在する可能性があり、
        それが原因で混乱や衝突が起きる可能性があります。なので、composition_idという名前はやめました。
    - parent: 更新後のCompositionのparent。ただし削除の場合、削除前のparent。
    - sort: 更新後のCompositionのsort。ただし削除の場合、削除前のsort。
    - part: 更新後のCompositionのpart。ただし削除の場合、削除前のpart。
    - quantity: 更新後のCompositionのquantity。ただし削除の場合、削除前のquantity。
    - action: 操作内容、'create','update','delete'のいずれかをセット。
    - timestamp: 構成履歴が作成された日時。
    """
    composition_change_set = models.ForeignKey(CompositionChangeSet, on_delete=models.CASCADE, related_name='composition_histories')
    composition_original_id = models.IntegerField()
    # composition = models.ForeignKey(Composition, on_delete=models.CASCADE)
    # parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    parent_original_id = models.BigIntegerField(null=True, blank=True)
    sort = models.IntegerField('並び順', null=True, blank=True)
    part = models.ForeignKey(Part, verbose_name='部品id', null=True, blank=True, on_delete=models.SET_NULL)
    quantity = models.IntegerField('数', null=True, blank=True, default=None)
    action = models.CharField('操作', max_length=50, choices=[
        ('create', '作成'),
        ('update', '更新'),
        ('delete', '削除')
    ])
    status = models.CharField('ステータス', max_length=6, choices=[
        ('before', '前'),
        ('after', '後')
    ])
    timestamp = models.DateTimeField('操作日時', auto_now_add=True)

    def __str__(self):
        return f'{self.action} at {self.timestamp} for Composition {self.composition.id}'

    class Meta:
        verbose_name = '構成履歴'
        db_table = "part_list_app_composition_history"


class UndoRedoPointer(models.Model):
    """
    UndoRedoPointer モデルは、製品毎の「元に戻す」、「やり直し」の構成履歴の起点
    を保持します。

    フィールド説明:
    - product: Composition インスタンスの製品(parent == null)外部キー。
    - pointer_id: 「元に戻す」、「やり直し」の構成履歴の起点id。
    - timestamp: UndoRedoPointerが作成された日時。
    """
    product = models.ForeignKey(Composition, on_delete=models.CASCADE, verbose_name='製品')
    # pointer_id = models.IntegerField()
    pointer = models.ForeignKey(CompositionChangeSet, on_delete=models.CASCADE)
    timestamp = models.DateTimeField('変更日時', auto_now_add=True)

    def __str__(self):
        return f'UndoRedoPointer at {self.timestamp}'

    class Meta:
        verbose_name = 'UndoRedoPointer'
        db_table = "part_list_app_undo_redo_pointer"


